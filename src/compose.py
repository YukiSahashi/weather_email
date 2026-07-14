"""記事生成のオーケストレーション。

2段階構成:
  1) 下書き生成    : 気象庁データ + ニュースを渡して記事化
  2) ファクトチェック: 下書きを気象庁データ・ニュースと突き合わせ、
                       データにない数値・警報・URLを除去した最終版を出力

「LLMによるファクトチェック」は、外部知識との照合ではなく
"与えた一次データとの整合チェック"として運用するのが要点。
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable

from . import llm

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
JST = dt.timezone(dt.timedelta(hours=9))


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def build_digest(cfg: dict, jma_block: str, news_block: str,
                 generate: Callable[..., str] | None = None) -> str:
    """generate はテスト用に差し替え可能(llm.generate と同じ引数)。"""
    gen = generate or (lambda prompt, system=None:
                       llm.generate(cfg, prompt, system))
    today = dt.datetime.now(JST).strftime("%Y年%m月%d日")
    system = load_prompt("system_prompt.txt")

    draft_prompt = load_prompt("draft_prompt.txt").format(
        date=today, jma_block=jma_block, news_block=news_block)
    draft = gen(draft_prompt, system)

    fc_prompt = load_prompt("fact_check_prompt.txt").format(
        date=today, jma_block=jma_block, news_block=news_block, draft=draft)
    final = gen(fc_prompt, system)
    return final.strip()
