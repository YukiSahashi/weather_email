"""スモークテスト。

使い方:
  pytest tests/smoke_test.py -v                    # 通常(ネットワークあり)
  SKIP_NETWORK=1 pytest tests/smoke_test.py -v     # オフライン(構成チェックのみ)

GEMINI_API_KEY が設定されているときだけ LLM の疎通テストも走る。
3層構成:
  1) オフライン: 設定・プロンプト・パイプライン配線(フェイクLLM)
  2) ネットワーク: 気象庁JSON・ニュースフィードの実取得
  3) LLM: Gemini への最小呼び出し
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import compose, jma, news  # noqa: E402
from src import main as app_main  # noqa: E402

SKIP_NETWORK = os.environ.get("SKIP_NETWORK") == "1"
needs_network = pytest.mark.skipif(SKIP_NETWORK, reason="SKIP_NETWORK=1")
needs_llm = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY 未設定")


@pytest.fixture(scope="module")
def cfg():
    return app_main.load_config(ROOT / "config.yaml")


# ---------- 1) オフライン ----------

def test_config_structure(cfg):
    assert set(cfg["jma"]["regions"]) == {"national", "east", "west"}
    for region in cfg["jma"]["regions"].values():
        assert region["areas"], "各リージョンに最低1地域が必要"
        for a in region["areas"]:
            assert a["code"].isdigit() and len(a["code"]) == 6, \
                f"地域コードは6桁数字: {a}"
    assert cfg["news"]["feeds"], "ニュースフィードが空"
    assert cfg["llm"]["models"], "LLMモデルリストが空"
    assert "{date}" in cfg["mail"]["subject_template"]


def test_prompts_exist_and_have_placeholders():
    required = {
        "system_prompt.txt": [],
        "draft_prompt.txt": ["{date}", "{jma_block}", "{news_block}"],
        "fact_check_prompt.txt": ["{date}", "{jma_block}", "{draft}"],
    }
    for name, placeholders in required.items():
        p = ROOT / "prompts" / name
        assert p.exists(), f"{name} がない"
        text = p.read_text(encoding="utf-8")
        assert text.strip(), f"{name} が空"
        for ph in placeholders:
            assert ph in text, f"{name} にプレースホルダ {ph} がない"


def test_pipeline_offline(cfg):
    """LLMをフェイクに差し替えて、下書き→ファクトチェックの配線を確認。"""
    calls: list[str] = []

    def fake_generate(prompt, system=None):
        calls.append(prompt)
        return "# フェイク記事\nテスト本文"

    out = compose.build_digest(
        cfg, "（気象庁データのダミー）", "（ニュースのダミー）",
        generate=fake_generate)
    assert "フェイク記事" in out
    assert len(calls) == 2, "下書き+ファクトチェックで2回呼ばれるはず"
    assert "気象庁データのダミー" in calls[0]
    assert "ニュースのダミー" in calls[0]
    assert "気象庁データのダミー" in calls[1], \
        "ファクトチェックにも気象庁データが渡るはず"


def test_jma_parse_forecast_tolerates_garbage():
    """予報JSONの形が想定外でも例外を出さない(概況で記事は成立するため)。"""
    assert jma.parse_forecast([]) == {"weather": [], "pops": [], "temps": []}
    assert jma.parse_forecast([{"timeSeries": [{"areas": []}]}])["weather"] == []


def test_news_text_block_empty():
    assert "見つかりませんでした" in news.to_text_block([])


# ---------- 2) ネットワーク ----------

@needs_network
def test_jma_fetch_one_area(cfg):
    a = cfg["jma"]["regions"]["east"]["areas"][0]
    res = jma.fetch_area(cfg, a["code"], a["name"])
    assert res["overview"] is not None, f"概況が取れない: {res.get('error')}"
    assert res["overview"]["text"], "概況テキストが空"
    block = jma.to_text_block(
        {"east": {"label": "東日本", "areas": [res]}})
    assert a["name"] in block


@needs_network
def test_news_feeds_reachable(cfg):
    items = news.collect(cfg)
    assert isinstance(items, list)  # 0件は許容(天気ニュースがない日もある)
    for it in items:
        assert it["title"] and it["link"].startswith("http")


# ---------- 3) LLM ----------

@needs_network
@needs_llm
def test_llm_roundtrip(cfg):
    from src import llm
    out = llm.generate(cfg, "「OK」とだけ返してください。")
    assert out.strip(), "LLM応答が空"
