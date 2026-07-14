name: daily-weather-digest

on:
  schedule:
    # JST 07:30 = UTC 22:30 (前日)。GitHubのcronは数分〜十数分遅延するため
    # 8:00必着に対しバッファを取っている。
    - cron: "30 22 * * *"
  workflow_dispatch: {}   # 手動実行ボタン(簡易Fetch!ボタンとしても使える)

jobs:
  build-and-send:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Generate digest and send mail
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          MAIL_TO: ${{ secrets.MAIL_TO }}
          MAIL_FROM: ${{ secrets.MAIL_FROM }}
        run: python -m src.main --output out/digest.md

      - name: Upload digest as artifact (バックアップ/デバッグ用)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: digest-${{ github.run_id }}
          path: out/
          retention-days: 14
