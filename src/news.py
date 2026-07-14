"""ニュースフィードから直近の天気関連記事を収集する。

役割は「補助情報」。数値の根拠には使わない(気象庁データが常に優先)。
本文取得は私的利用(著作権法30条: 個人的又は家庭内その他これに準ずる
限られた範囲)を前提とする。配信先を家族の外に広げる場合は要再検討。
"""
from __future__ import annotations

import datetime as dt
import time

import feedparser
import requests

try:
    import trafilatura
except ImportError:  # 本文抽出はオプション
    trafilatura = None

HEADERS = {"User-Agent": "weather-digest/1.0 (personal use)"}
TIMEOUT = 20
MAX_BODY_CHARS = 4000


def _entry_datetime(entry) -> dt.datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return dt.datetime.fromtimestamp(time.mktime(t), tz=dt.timezone.utc)
    return None


def fetch_feed(url: str):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return feedparser.parse(r.content)


def collect(cfg: dict) -> list[dict]:
    """設定されたフィードを巡回し、キーワード＋時間窓でフィルタする。"""
    news_cfg = cfg["news"]
    window = dt.timedelta(hours=cfg["app"]["news_window_hours"])
    now = dt.datetime.now(dt.timezone.utc)
    keywords = news_cfg["keywords"]
    seen_links: set[str] = set()
    items: list[dict] = []

    for feed in news_cfg["feeds"]:
        parsed = None
        for url in (feed.get("url"), feed.get("fallback_url")):
            if not url:
                continue
            try:
                candidate = fetch_feed(url)
                if candidate.entries:
                    parsed = candidate
                    break
            except Exception:  # noqa: BLE001
                continue
        if parsed is None:
            print(f"  [warn] フィード取得失敗: {feed['name']}")
            continue

        for e in parsed.entries:
            title = e.get("title", "") or ""
            summary = e.get("summary", "") or ""
            link = e.get("link", "") or ""
            if not link or link in seen_links:
                continue
            published = _entry_datetime(e)
            if published is not None and now - published > window:
                continue
            if not any(k in title or k in summary for k in keywords):
                continue
            seen_links.add(link)
            items.append({
                "source": feed["name"],
                "title": title,
                "link": link,
                "published": published.isoformat() if published else None,
                "summary": summary,
                "body": None,
            })

    items = items[: cfg["app"]["max_articles"]]

    if news_cfg.get("fetch_article_body") and trafilatura is not None:
        for it in items:
            it["body"] = fetch_body(it["link"])
    return items


def fetch_body(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        text = trafilatura.extract(r.text, include_comments=False)
        if not text:
            return None
        if len(text) > MAX_BODY_CHARS:
            text = text[:MAX_BODY_CHARS] + "…"
        return text
    except Exception:  # noqa: BLE001
        return None


def to_text_block(items: list[dict]) -> str:
    """LLMに渡す「ニュース」テキストブロックを組み立てる。"""
    if not items:
        return "（直近の対象時間内に該当するニュースは見つかりませんでした）"
    lines: list[str] = []
    for i, it in enumerate(items, 1):
        lines.append(
            f"[{i}] {it['title']}（{it['source']} / {it['published'] or '日時不明'}）")
        lines.append(f"    URL: {it['link']}")
        if it.get("body"):
            lines.append("    本文抜粋:")
            for ln in it["body"].splitlines()[:20]:
                if ln.strip():
                    lines.append(f"      {ln.strip()}")
        elif it.get("summary"):
            lines.append(f"    要旨: {it['summary']}")
        lines.append("")
    return "\n".join(lines)
