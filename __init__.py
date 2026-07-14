"""気象庁(JMA)の公開JSONから予報データを取得する。

数値・警報・概況の「唯一の根拠」となる一次情報源。
- overview_forecast: 予報官が書く天気概況テキスト
- forecast: 天気・降水確率・気温の構造化データ
"""
from __future__ import annotations

import requests

HEADERS = {"User-Agent": "weather-digest/1.0 (personal use)"}
TIMEOUT = 20


def fetch_json(url: str) -> dict | list:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_area(cfg: dict, code: str, name: str) -> dict:
    """1地域ぶんの概況+予報を取得する。片方が失敗しても続行する。"""
    ov_url = cfg["jma"]["endpoints"]["overview"].format(area=code)
    fc_url = cfg["jma"]["endpoints"]["forecast"].format(area=code)
    result: dict = {"code": code, "name": name,
                    "overview": None, "forecast": None, "error": None}
    try:
        ov = fetch_json(ov_url)
        result["overview"] = {
            "office": ov.get("publishingOffice"),
            "reportDatetime": ov.get("reportDatetime"),
            "headline": (ov.get("headlineText") or "").strip(),
            "text": (ov.get("text") or "").strip(),
        }
    except Exception as e:  # noqa: BLE001
        result["error"] = f"overview取得失敗: {e}"
    try:
        fc = fetch_json(fc_url)
        result["forecast"] = parse_forecast(fc)
    except Exception as e:  # noqa: BLE001
        prev = result["error"] or ""
        result["error"] = f"{prev} forecast取得失敗: {e}".strip()
    return result


def parse_forecast(fc: list) -> dict:
    """短期予報(先頭要素)から天気・降水確率・気温を best-effort で抽出する。

    気象庁JSONは timeSeries の並びが将来変わり得るので、キーの有無で判別し、
    解釈できない部分は黙って捨てる(概況テキストがあれば記事は成立する)。
    """
    out: dict = {"weather": [], "pops": [], "temps": []}
    try:
        short = fc[0]
        for ts in short.get("timeSeries", []):
            areas = ts.get("areas", [])
            if not areas:
                continue
            a0 = areas[0]
            times = ts.get("timeDefines", [])
            if "weathers" in a0:
                out["weather"] = [{"time": t, "text": w}
                                  for t, w in zip(times, a0["weathers"])]
            elif "pops" in a0:
                out["pops"] = [{"time": t, "pop": p}
                               for t, p in zip(times, a0["pops"])]
            elif "temps" in a0:
                out["temps"] = [{"time": t, "temp": v}
                                for t, v in zip(times, a0["temps"])]
    except Exception:  # noqa: BLE001
        pass
    return out


def fetch_all(cfg: dict) -> dict:
    regions = {}
    for key, region in cfg["jma"]["regions"].items():
        areas = [fetch_area(cfg, a["code"], a["name"]) for a in region["areas"]]
        regions[key] = {"label": region["label"], "areas": areas}
    return regions


def to_text_block(regions: dict) -> str:
    """LLMに渡す「気象庁データ」テキストブロックを組み立てる。"""
    lines: list[str] = []
    for region in regions.values():
        lines.append(f"■ {region['label']}")
        for a in region["areas"]:
            lines.append(f"◎ {a['name']}（気象庁 地域コード {a['code']}）")
            if a.get("error"):
                lines.append(f"  [取得エラー] {a['error']}")
            ov = a.get("overview")
            if ov and ov["text"]:
                if ov["headline"]:
                    lines.append(f"  見出し: {ov['headline']}")
                lines.append(
                    f"  概況（{ov['reportDatetime']} {ov['office']}発表）:")
                for ln in ov["text"].splitlines():
                    if ln.strip():
                        lines.append(f"    {ln.strip()}")
            fcst = a.get("forecast") or {}
            if fcst.get("weather"):
                w = fcst["weather"][0]
                lines.append(f"  本日の天気: {w['text']}")
            pops = [p for p in fcst.get("pops", []) if p["pop"] != ""]
            if pops:
                s = " / ".join(f"{p['time'][11:16]}〜 {p['pop']}%"
                               for p in pops[:4])
                lines.append(f"  降水確率: {s}")
            temps = [t for t in fcst.get("temps", []) if t["temp"] != ""]
            if temps:
                s = " / ".join(f"{t['time'][5:10]} {t['temp']}℃"
                               for t in temps[:4])
                lines.append(f"  予想気温: {s}")
            lines.append("")
    return "\n".join(lines)
