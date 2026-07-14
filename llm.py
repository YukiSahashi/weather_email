"""エントリポイント。

使い方:
  python -m src.main                      # 取得→生成→メール送信
  python -m src.main --dry-run            # 送信せず標準出力とファイルに書くだけ
  python -m src.main --no-news            # 気象庁データのみで生成
  python -m src.main --output out/x.md    # 保存先を指定
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml

from . import compose, jma, mailer, news

JST = dt.timezone(dt.timedelta(hours=9))


def load_config(path: str | Path = "config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def run(dry_run: bool = False, no_news: bool = False,
        output: str | None = "out/digest.md",
        config_path: str = "config.yaml") -> int:
    cfg = load_config(config_path)

    print("[1/4] 気象庁データ取得...")
    regions = jma.fetch_all(cfg)
    jma_block = jma.to_text_block(regions)
    n_err = sum(1 for r in regions.values()
                for a in r["areas"] if a.get("error"))
    if n_err:
        print(f"  [warn] {n_err} 地域で取得エラー(残りのデータで続行)")

    print("[2/4] ニュース取得...")
    items = [] if no_news else news.collect(cfg)
    news_block = news.to_text_block(items)
    print(f"  対象記事 {len(items)} 件")

    print("[3/4] LLMで記事生成(下書き → ファクトチェック)...")
    digest = compose.build_digest(cfg, jma_block, news_block)

    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(digest + "\n", encoding="utf-8")
        print(f"  保存: {p}")

    if dry_run:
        print("[4/4] --dry-run のため送信をスキップ")
        print("=" * 60)
        print(digest)
        return 0

    print("[4/4] メール送信...")
    subject = cfg["mail"]["subject_template"].format(date=today)
    mailer.send(cfg, subject, digest)
    print("  送信完了")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="天気ダイジェスト生成・送信")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--output", default="out/digest.md")
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()
    sys.exit(run(a.dry_run, a.no_news, a.output, a.config))


if __name__ == "__main__":
    main()
