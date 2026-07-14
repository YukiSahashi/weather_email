name: smoke-test

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch: {}

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      # ネットワークテスト込みで実行。
      # GEMINI_API_KEY を設定していればLLM疎通テストも走る(未設定ならskip)。
      - name: Run smoke tests
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: pytest tests/smoke_test.py -v
