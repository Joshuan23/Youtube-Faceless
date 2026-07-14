"""SEO metadata generator: titles, descriptions, tags, chapters."""

import json
import logging

from .llm import chat, parse_json

logger = logging.getLogger(__name__)

_NICHE_TAGS = {
    "nursery_rhymes": ["nursery rhymes","kids songs","nursery rhymes for babies",
        "songs for children","baby songs","sing along","toddler songs","preschool songs",
        "children songs","kids music","nursery rhymes for kids","rhymes for babies",
        "kids sing along","fun songs for kids","learning songs for toddlers"],
    "lullabies": ["lullaby","lullabies for babies","baby sleep music","bedtime songs",
        "sleep music for babies","soothing songs","calm baby music","lullaby songs",
        "bedtime lullaby","baby lullaby","sleepy time songs","nursery lullabies",
        "songs to sleep","gentle music for kids","relaxing baby music"],
    "learning_songs": ["learning songs","abc song","counting song","educational songs for kids",
        "toddler learning","preschool learning","alphabet song","numbers song","colors song",
        "songs for toddlers","kids educational videos","learn with songs","early learning",
        "nursery learning songs","fun learning for kids"],
}

SYSTEM_PROMPT = """\
You are a YouTube specialist for a children's nursery rhyme channel (audience: parents
choosing videos for toddlers). You maximize kid-friendly discovery through:
- Cheerful, searchable titles under 70 characters (include "Nursery Rhymes" / "Kids Songs")
- Warm, wholesome descriptions parents trust (300-400 words) with natural keywords
- Simple, relevant tags (15, mix of broad + long-tail kids-song terms)

Everything must be 100% wholesome and appropriate for young children.
Never use clickbait, fear, or anything scary. No purchase or subscribe pressure.
"""


class SEOOptimizer:
    def generate(self, script_data: dict) -> dict:
        """
        Given a script dict (with title, sections, key_takeaways, niche, topic),
        return SEO metadata.
        """
        topic = script_data.get("topic", "")
        niche = script_data.get("niche", "nursery_rhymes")
        title = script_data.get("title", topic)
        takeaways = script_data.get("key_takeaways", [])
        sections = script_data.get("sections", [])

        prompt = f"""
Create kid-friendly YouTube metadata for a children's nursery rhyme video.

Current title: {title}
Song theme: {topic}
Style: {niche}
Learning moments: {json.dumps(takeaways)}
Song sections: {json.dumps([s.get("name", "") for s in sections])}

Generate:
1. 3 cheerful title variations (under 70 chars each, include "Nursery Rhymes" or "Kids Songs")
2. A warm, wholesome description (300-400 words) parents trust: a friendly intro,
   what little ones will enjoy/learn, gentle reminder that all content is made for kids,
   ending with kid-song hashtags. No scary or clickbait language.
3. 15 tags (mix: broad + long-tail children's-song terms)

Return a JSON object:
{{
  "titles": ["...", "...", "..."],
  "recommended_title": "...",
  "description": "...",
  "tags": ["...", ...],
  "chapters": [],
  "hashtags": ["#NurseryRhymes", "#KidsSongs", ...]
}}
"""
        raw = chat(SYSTEM_PROMPT, prompt, max_tokens=2048)
        seo = parse_json(raw)
        logger.info("SEO generated for: %s", seo.get("recommended_title"))
        return seo

    def generate_speed(self, script_data: dict) -> dict:
        """Instant SEO — zero LLM calls, uses predefined keyword lists."""
        topic = script_data.get("topic", "")
        niche = script_data.get("niche", "nursery_rhymes")
        title = script_data.get("title", topic)
        tags  = _NICHE_TAGS.get(niche) or next(iter(_NICHE_TAGS.values()))
        style = niche.replace("_", " ")
        description = (
            f"🌟 Sing along to {topic}! 🌟\n\n"
            f"Join Twinkle Tots for cheerful {style} that little ones love. "
            f"Perfect for playtime, story time, and sing-along fun with the whole family.\n\n"
            f"👶 This video is made for kids and completely wholesome.\n"
            f"🎵 New nursery rhymes and songs added regularly!\n\n"
            + " ".join(f"#{t.title().replace(' ','')}" for t in tags[:6])
        )
        return {
            "recommended_title": title,
            "description": description,
            "tags": tags,
            "chapters": [],
            "hashtags": [f"#{t.title().replace(' ','')}" for t in tags[:6]],
        }

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
