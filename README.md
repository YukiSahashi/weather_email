# weather-digest

毎朝、気象庁の一次データ＋直近24時間のニュースをLLM（Gemini）で記事化し、メールで届ける個人用パイプライン。GitHub Actions のみで動作し、追加サーバは不要。

## 仕組み

```
GitHub Actions (cron: UTC 22:30 = JST 07:30)
  1. 気象庁 予報JSON + 概況 → 事実データ（数値・警報の唯一の根拠）
  2. ニュースRSS（NHK等）→ 直近24h・天気キーワードで絞り込み → 本文抽出
  3. Gemini Flash: 下書き生成 → 気象庁データと突き合わせるファクトチェック
  4. SMTP でメール送信（本文はMarkdown + HTML）
```

設計上の要点:

- 数値・警報は気象庁データのみを根拠とし、LLMには創作を許さない（`prompts/system_prompt.txt`）
- 「ファクトチェック」は外部知識との照合ではなく、下書きと一次データの整合チェック（`prompts/fact_check_prompt.txt`）
- LLMは `config.yaml` の `llm.models` を上から順に試すフォールバック方式（簡易モデルルーティング）
- ニュース取得は補助情報。フィードが全滅しても気象庁データだけで記事は成立する

## セットアップ

1. このディレクトリをGitHubリポジトリとしてpush（Privateを推奨）
2. リポジトリの Settings → Secrets and variables → Actions に以下を登録

| Secret | 内容 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio で発行 |
| `SMTP_HOST` | 例: `smtp.gmail.com` |
| `SMTP_PORT` | `465`（SSL）または `587`（STARTTLS） |
| `SMTP_USER` | 送信元メールアドレス |
| `SMTP_PASSWORD` | Gmailの場合は「アプリパスワード」（2段階認証の有効化が必要） |
| `MAIL_TO` | 宛先（カンマ区切りで複数可） |
| `MAIL_FROM` | 省略可。省略時は `SMTP_USER` |

3. Actions タブ → `daily-weather-digest` → `Run workflow` で手動実行して動作確認
4. 以後、毎朝 JST 7:30 頃に自動実行 → 8:00 前後に着信

## ローカルでの実行・テスト

```bash
pip install -r requirements.txt

# オフラインテスト（ネットワーク・APIキー不要）
SKIP_NETWORK=1 pytest tests/smoke_test.py -v

# フルテスト（気象庁・RSSの実取得。GEMINI_API_KEYがあればLLM疎通も）
pytest tests/smoke_test.py -v

# 送信せずに記事だけ生成して確認
export GEMINI_API_KEY=...
python -m src.main --dry-run
```

## カスタマイズ

すべて `config.yaml` で完結します。

- 対象地域の変更: `jma.regions` の地域コードを編集（コード一覧は https://www.jma.go.jp/bosai/common/const/area.json ）
- ニュースソースの追加/削除: `news.feeds` にRSSのURLを追記
- 記事の絞り込み: `news.keywords` / `app.news_window_hours` / `app.max_articles`
- モデルの変更: `llm.models`（上から順に試行）
- 文体・構成の変更: `prompts/` の3ファイル

## 既知の制約と注意

- GitHub Actions の cron は指定時刻から数分〜十数分遅延することがある。厳密な定時配信は保証されない
- NHKのRSSは2025年秋のサイト移行でURLが変わった経緯があり、今後も変わりうる。フィード取得失敗時は警告を出して気象庁データのみで続行する
- ニュース本文の取得・要約は私的利用（自分＋家庭内相当の範囲）を前提とした設計。配信先を家族の外に広げる場合は、本文取得（`news.fetch_article_body: false`）を切り、要約の扱いを見直すこと
- 気象庁JSONは公式に案内されたAPIではないため、構造変更がありうる。パーサは概況テキスト優先のbest-effortにしてある
