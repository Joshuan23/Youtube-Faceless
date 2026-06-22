"""Trending topic discovery for each niche."""

import os
import json
import random
import logging
from datetime import datetime

import anthropic
import yaml

logger = logging.getLogger(__name__)

_CONFIG = None


def _config():
    global _CONFIG
    if _CONFIG is None:
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        with open(cfg_path) as f:
            _CONFIG = yaml.safe_load(f)
    return _CONFIG


SEED_TOPICS: dict[str, list[str]] = {
    "personal_finance": [
        "how to save $1000 fast",
        "investing with $100",
        "passive income ideas 2025",
        "budgeting for beginners",
        "how to pay off debt quickly",
        "best index funds",
        "how to build an emergency fund",
        "credit score secrets banks hide",
        "7 money habits of millionaires",
        "how to negotiate your salary",
        "compound interest explained",
        "roth ira vs 401k",
        "how to start investing at 20",
        "real estate investing with no money",
        "living below your means",
        "money mistakes to avoid in your 30s",
        "how to make $500 a week online",
        "dividend investing for beginners",
        "tax saving strategies",
        "financial freedom at 40",
    ],
    "ai_tech": [
        "AI tools replacing jobs in 2025",
        "10 ChatGPT prompts for productivity",
        "make $500/day with AI",
        "AI vs human creativity",
        "best free AI tools",
        "Claude vs ChatGPT vs Gemini",
        "AI images: making money with Midjourney",
        "automation with AI",
        "AI side hustle ideas",
        "future jobs AI cannot replace",
    ],
    "business": [
        "how to start a business with $0",
        "most profitable online businesses",
        "dropshipping in 2025",
        "affiliate marketing for beginners",
        "how to scale to 6 figures",
        "business ideas with low startup cost",
        "freelancing secrets",
        "how to build a personal brand",
        "digital products that sell",
        "Shopify store launch guide",
    ],
    "health": [
        "morning routine that changed my life",
        "habits of the healthiest people",
        "foods that fight inflammation",
        "how to sleep better",
        "intermittent fasting results",
        "mental health daily habits",
        "exercise with no equipment",
        "longevity secrets from blue zones",
        "stress reduction techniques",
        "gut health transformation",
    ],
}


def get_trending_topics(niche: str, count: int = 5) -> list[str]:
    """
    Returns a list of video topic ideas for the given niche.
    Tries Google Trends via pytrends; falls back to Claude-generated ideas,
    then the local seed list.
    """
    topics = _claude_topic_ideas(niche, count)
    if topics:
        return topics
    seed = SEED_TOPICS.get(niche, SEED_TOPICS["personal_finance"])
    random.shuffle(seed)
    return seed[:count]


def _claude_topic_ideas(niche: str, count: int) -> list[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return []
    try:
        client = anthropic.Anthropic(api_key=api_key)
        today = datetime.utcnow().strftime("%B %Y")
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"You are a YouTube strategist. Today is {today}.\n\n"
                        f"Generate {count} high-potential YouTube video topic ideas for the '{niche}' niche.\n"
                        "Requirements:\n"
                        "- Each topic must be a punchy, searchable title under 70 characters\n"
                        "- Mix evergreen + trending angles\n"
                        "- Focus on high click-through-rate hooks\n"
                        "- Include numbers where natural (e.g. '7 ways...')\n\n"
                        "Return ONLY a JSON array of strings, no explanation."
                    ),
                }
            ],
        )
        raw = message.content[0].text.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        logger.warning("Claude topic generation failed: %s", e)
        return []
