"""SEO metadata generator: titles, descriptions, tags, chapters."""

import os
import json
import logging
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a YouTube SEO specialist. You maximize organic discovery through:
- Keyword-rich titles under 70 characters
- Long-form descriptions (400-500 words) packed with LSI keywords
- Strategic tag selection (15 tags, mix of broad + long-tail)
- Chapter timestamps for watch time retention

Always prioritize click-through rate and search ranking simultaneously.
"""


class SEOOptimizer:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(self, script_data: dict) -> dict:
        """
        Given a script dict (with title, sections, key_takeaways, niche, topic),
        return SEO metadata.
        """
        topic = script_data.get("topic", "")
        niche = script_data.get("niche", "personal_finance")
        title = script_data.get("title", topic)
        takeaways = script_data.get("key_takeaways", [])
        sections = script_data.get("sections", [])

        prompt = f"""
Optimize YouTube SEO metadata for this video.

Current title: {title}
Topic: {topic}
Niche: {niche}
Key takeaways: {json.dumps(takeaways)}
Section names: {json.dumps([s.get("name", "") for s in sections])}

Generate:
1. A/B test 3 title variations (under 70 chars each)
2. Full video description (400-500 words, includes keywords naturally,
   has "In this video" intro, bullet points of what you'll learn,
   ends with generic subscribe CTA and hashtags)
3. 15 tags (mix: broad + niche + long-tail)
4. Chapter timestamps (assume video starts at 0:00, first chapter at 0:00)

Return a JSON object:
{{
  "titles": ["...", "...", "..."],
  "recommended_title": "...",
  "description": "...",
  "tags": ["...", ...],
  "chapters": [
    {{"time": "0:00", "label": "Introduction"}},
    ...
  ],
  "hashtags": ["#Finance", ...]
}}
"""
        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]
        seo = json.loads(raw)
        logger.info("SEO generated for: %s", seo.get("recommended_title"))
        return seo

    def build_full_description(self, seo: dict) -> str:
        desc = seo.get("description", "")
        chapters = seo.get("chapters", [])
        if chapters:
            chapter_text = "\n".join(
                f"{c['time']} {c['label']}" for c in chapters
            )
            desc = desc + "\n\n⏱️ CHAPTERS\n" + chapter_text
        hashtags = seo.get("hashtags", [])
        if hashtags:
            desc = desc + "\n\n" + " ".join(hashtags)
        return desc
