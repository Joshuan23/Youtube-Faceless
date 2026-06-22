"""SEO metadata generator: titles, descriptions, tags, chapters."""

import json
import logging

from .llm import chat, parse_json

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
        raw = chat(SYSTEM_PROMPT, prompt, max_tokens=2048)
        seo = parse_json(raw)
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
