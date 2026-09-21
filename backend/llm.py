"""
llm.py

Thin OpenRouter client used by the two optional LLM layers (document
extraction in ingestion.py and the root-cause narrative in rca.py).
Everything else in the pipeline runs without it.

Configuration comes from the environment or a `.env` file in the repo root:
  OPENROUTER_API_KEY   required for any LLM call
  OPENROUTER_MODEL     optional, one model id or a comma-separated list tried in
                       order (free models get rate-limited, so the next one steps in)
"""

import os
import time

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = ("nvidia/nemotron-3-super-120b-a12b:free,openrouter/free,"
                 "google/gemma-4-31b-it:free,qwen/qwen3.8-27b:free")


def model_list():
    return [m.strip() for m in (os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL).split(",")]


def chat(messages, system=None, tools=None, tool_choice=None, max_tokens=1024, model=None, timeout=60):
    """Send one chat completion request and return the assistant message dict."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (put it in .env or the environment)")

    models = [model] if model else model_list()
    payload = {
        "max_tokens": max_tokens,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

    last_err = None
    for attempt in range(2):
        for m in models:
            try:
                resp = requests.post(API_URL, json=dict(payload, model=m), timeout=timeout,
                                     headers={"Authorization": f"Bearer {key}"})
                if resp.status_code in (401, 403):
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code in (401, 403):
                    raise
                last_err = e
            except (requests.RequestException, KeyError, IndexError) as e:
                last_err = e
        time.sleep(3)
    raise RuntimeError(f"all models failed, last error: {last_err}")
