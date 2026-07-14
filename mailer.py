"""Gemini API 呼び出し。config.yaml の models を上から順に試す簡易ルーティング。

- 各モデル2回までリトライ(指数的に待機)
- 全滅したら LLMError
- APIキーは環境変数 GEMINI_API_KEY からのみ取得(コードに書かない)
"""
from __future__ import annotations

import json
import os
import time

import requests

API_URL = ("https://generativelanguage.googleapis.com/v1beta/"
           "models/{model}:generateContent")
TIMEOUT = 120


class LLMError(RuntimeError):
    pass


def generate(cfg: dict, prompt: str, system: str | None = None) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("環境変数 GEMINI_API_KEY が未設定です")

    last_err: Exception | None = None
    for model in cfg["llm"]["models"]:
        for attempt in range(2):
            try:
                return _call(model, api_key, prompt, system, cfg)
            except LLMError as e:
                last_err = e
                print(f"  [warn] {model} 失敗(試行{attempt + 1}): {e}")
                time.sleep(2 * (attempt + 1))
    raise LLMError(f"全モデルで生成に失敗しました: {last_err}")


def _call(model: str, api_key: str, prompt: str,
          system: str | None, cfg: dict) -> str:
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": cfg["llm"].get("temperature", 0.3),
            "maxOutputTokens": cfg["llm"].get("max_output_tokens", 2048),
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    r = requests.post(API_URL.format(model=model),
                      params={"key": api_key}, json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        raise LLMError(f"{model}: HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise LLMError(
            f"{model}: 応答形式が不正: {json.dumps(data, ensure_ascii=False)[:300]}")
