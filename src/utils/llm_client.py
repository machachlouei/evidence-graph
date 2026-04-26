from __future__ import annotations

import os
import re
import time
from typing import Literal

TaskType = Literal["edge", "default"]

_gemini_client = None
_groq_client = None
_gemini_quota_exhausted = False  # set True on daily quota hit; triggers Groq fallback


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    return _gemini_client


def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


def _groq_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def chat(
    system: str,
    user_prompt: str,
    max_tokens: int = 2048,
    task_type: TaskType = "default",
) -> str:
    """Route LLM calls by task type:
      - task_type='edge'    → Groq llama-3.1-8b-instant (high volume, ~14400/day free)
      - task_type='default' → Gemini 2.5 Flash Lite, falls back to Groq llama-3.3-70b-versatile
                              when Gemini daily quota is exhausted
    """
    if task_type == "edge":
        return _chat_groq(system, user_prompt, max_tokens, model="llama-3.1-8b-instant")
    return _chat_gemini_with_fallback(system, user_prompt, max_tokens)


def _chat_gemini_with_fallback(system: str, user_prompt: str, max_tokens: int) -> str:
    global _gemini_quota_exhausted

    if not _gemini_quota_exhausted:
        try:
            return _chat_gemini(system, user_prompt, max_tokens)
        except RuntimeError as e:
            if "daily quota exhausted" in str(e):
                if _groq_available():
                    _gemini_quota_exhausted = True
                    print("  [llm] Gemini daily quota hit — switching to Groq llama-3.3-70b-versatile")
                else:
                    raise
            else:
                raise

    return _chat_groq(system, user_prompt, max_tokens, model="llama-3.3-70b-versatile")


# ── Groq ─────────────────────────────────────────────────────────────────────

_groq_last_call: float = 0.0
_GROQ_MIN_INTERVAL = 2.4  # 30 RPM free tier → 1 call per 2s; 2.4s gives headroom


def _groq_throttle() -> None:
    global _groq_last_call
    elapsed = time.monotonic() - _groq_last_call
    if elapsed < _GROQ_MIN_INTERVAL:
        time.sleep(_GROQ_MIN_INTERVAL - elapsed)
    _groq_last_call = time.monotonic()


def _chat_groq(system: str, user_prompt: str, max_tokens: int, model: str) -> str:
    from groq import RateLimitError

    client = _get_groq()
    for attempt in range(4):
        _groq_throttle()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.0,
            )
            return response.choices[0].message.content.strip()
        except RateLimitError:
            if attempt < 3:
                time.sleep(15 * (attempt + 1))
            else:
                raise
        except Exception:
            raise


# ── Gemini ────────────────────────────────────────────────────────────────────

def _chat_gemini(system: str, user_prompt: str, max_tokens: int) -> str:
    from google.genai import types
    from google.genai.errors import ClientError

    client = _get_gemini()
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model="models/gemini-2.5-flash-lite",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    temperature=0.0,
                ),
            )
            text = response.text
            if text is None:
                parts = response.candidates[0].content.parts
                text = "".join(p.text for p in parts if hasattr(p, "text") and p.text)
            return text.strip()

        except ClientError as e:
            if e.code != 429:
                raise
            msg = str(e)
            if "GenerateRequestsPerDayPerProjectPerModel" in msg:
                raise RuntimeError(
                    "Gemini daily quota exhausted (20 req/day free tier). "
                    "Wait until tomorrow or add GROQ_API_KEY to handle more calls."
                ) from e
            # Per-minute rate limit — wait the suggested delay
            retry_delay = 60
            m = re.search(r'"retryDelay":\s*"(\d+)', msg)
            if m:
                retry_delay = int(m.group(1)) + 2
            if attempt < 3:
                time.sleep(retry_delay)
            else:
                raise
