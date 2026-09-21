"""
llm.py

Thin OpenRouter client used by the two optional LLM layers (document
extraction in ingestion.py and the root-cause narrative in rca.py).
Everything else in the pipeline runs without it.

Configuration comes from the environment or a `.env` file in the repo root:
  OPENROUTER_API_KEY   required for any LLM call
  OPENROUTER_MODEL     optional, defaults to DEFAULT_MODEL
"""

import os

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def chat(messages, system=None, tools=None, tool_choice=None, max_tokens=1024, model=None, timeout=60):
    """Send one chat completion request and return the assistant message dict."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (put it in .env or the environment)")

    payload = {
        "model": model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
        "max_tokens": max_tokens,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

    resp = requests.post(API_URL, json=payload, timeout=timeout,
                         headers={"Authorization": f"Bearer {key}"})
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]
