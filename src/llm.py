"""
Unified LLM client. Auto-detects which provider to use based on env vars.

Priority (free first):
  1. Groq      – free tier, Llama 3.3 70B  (GROQ_API_KEY)
  2. Gemini    – free tier, Gemini 1.5 Flash (GEMINI_API_KEY)
  3. Claude    – paid, highest quality       (ANTHROPIC_API_KEY)
  4. OpenAI    – paid                        (OPENAI_API_KEY)
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_FAST_MODEL = "llama-3.1-8b-instant"   # ~5x faster, used in speed mode
GEMINI_MODEL    = "gemini-1.5-flash"
CLAUDE_MODEL    = "claude-sonnet-4-6"
OPENAI_MODEL    = "gpt-4o-mini"


def _detect() -> str:
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise EnvironmentError(
        "No LLM API key found.\n"
        "Free option: get a Groq key at https://console.groq.com (no credit card)\n"
        "Then add to .env:  GROQ_API_KEY=gsk_xxxxxxxxxxxx"
    )


def chat(system: str, user: str, max_tokens: int = 4096) -> str:
    """Send a chat message and return the text response."""
    provider = _detect()
    if provider == "groq":
        return _groq(system, user, max_tokens, GROQ_MODEL)
    if provider == "gemini":
        return _gemini(system, user, max_tokens)
    if provider == "claude":
        return _claude(system, user, max_tokens)
    return _openai(system, user, max_tokens)


def chat_fast(system: str, user: str, max_tokens: int = 1024) -> str:
    """Fast chat using the smallest/quickest available model."""
    provider = _detect()
    if provider == "groq":
        return _groq(system, user, max_tokens, GROQ_FAST_MODEL)
    if provider == "gemini":
        return _gemini(system, user, max_tokens)
    if provider == "claude":
        return _claude(system, user, max_tokens)
    return _openai(system, user, max_tokens)


def active_provider() -> str:
    try:
        return _detect()
    except EnvironmentError:
        return "none"


def parse_json(text: str) -> dict | list:
    """
    Robustly parse JSON from LLM output.

    Groq/Llama has two common failure modes:
    1. Wraps output in ```json ... ``` fences
    2. Puts literal newlines/tabs inside JSON string values (invalid per spec)
    """
    import re
    text = text.strip()

    # strip code fences
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Escape literal newlines/tabs that are inside JSON string values.
    # Walk char-by-char tracking whether we're inside a string.
    text = _escape_string_literals(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: pull out the outermost { } block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def _escape_string_literals(text: str) -> str:
    """Replace bare newlines/tabs/control-chars inside JSON string values."""
    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            # already-escaped sequence — pass both chars through unchanged
            result.append(ch)
            result.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string:
            if ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            elif ord(ch) < 0x20:        # other control chars → drop
                pass
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1
    return "".join(result)


# ── Providers ──────────────────────────────────────────────────────────────

def _groq(system: str, user: str, max_tokens: int, model: str = GROQ_MODEL) -> str:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content


def _gemini(system: str, user: str, max_tokens: int) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system,
        generation_config={"max_output_tokens": max_tokens},
    )
    resp = model.generate_content(user)
    return resp.text


def _claude(system: str, user: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def _openai(system: str, user: str, max_tokens: int) -> str:
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content
