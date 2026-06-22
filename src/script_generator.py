"""Claude-powered YouTube script generator."""

import os
import json
import logging
from pathlib import Path

import anthropic
import yaml

logger = logging.getLogger(__name__)


def _load_config():
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


SYSTEM_PROMPT = """\
You are a world-class YouTube scriptwriter specializing in faceless educational channels.
You write scripts that:
- Hook viewers in the first 15 seconds (pattern interrupt)
- Deliver dense, useful information with storytelling
- Use conversational, energetic language (no filler phrases)
- Target 10-14 minutes of spoken content at 140 words/minute
- Include strategic retention hooks ("stick around because...")
- End with a strong subscribe + bell CTA

Never start a sentence with "I" referring to the channel. Use "you" and "we".
Always speak to the viewer's desire for transformation.
"""

SCRIPT_TEMPLATE = """\
Write a complete, word-for-word YouTube script for a faceless channel in the '{niche}' niche.

Topic: "{topic}"
Target length: {target_length} minutes (≈{target_words} words)
Niche average CPM: ${cpm}/1000 views (emphasize value to audience)

Structure the script with these clearly labeled sections:

[HOOK] (first 15-30 seconds)
- Shocking stat, bold claim, or provocative question
- "By the end of this video you will know exactly how to..."

[INTRO] (30 seconds – 1.5 minutes)
- Establish credibility of the information
- Preview the key points (3-5 numbered items)
- Brief retention hook

[SECTION 1: {s1}]
- Deep dive, data, examples, mini-story

[SECTION 2: {s2}]
- Deep dive, data, examples

[SECTION 3: {s3}]
- Deep dive, data, examples

[SECTION 4: {s4}] (if needed)

[RECAP & CTA] (last 45-60 seconds)
- Summarize top 3 takeaways
- Soft sell: "If you found this valuable, subscribe..."
- Tease next video

Return a JSON object with these keys:
{{
  "title": "...",
  "hook_line": "...",
  "sections": [
    {{"name": "...", "content": "...", "duration_sec": 120}},
    ...
  ],
  "full_script": "...",
  "word_count": 1850,
  "estimated_duration_min": 13.2,
  "key_takeaways": ["...", "...", "..."]
}}
"""

SECTION_TEMPLATES: dict[str, list[str]] = {
    "personal_finance": [
        "The Problem Nobody Talks About",
        "The Strategy That Actually Works",
        "Step-by-Step Implementation",
        "Common Mistakes to Avoid",
        "Real-World Results",
    ],
    "ai_tech": [
        "Why This Changes Everything",
        "How It Actually Works",
        "Practical Use Cases",
        "Pitfalls and Limitations",
        "What Comes Next",
    ],
    "business": [
        "The Opportunity Nobody Sees",
        "The Blueprint",
        "Getting Your First Win",
        "Scaling Up",
        "Advanced Tactics",
    ],
    "health": [
        "The Science Behind It",
        "What Most People Get Wrong",
        "The Protocol That Works",
        "Tracking Your Progress",
        "Sustainable Long-Term Habits",
    ],
}


class ScriptGenerator:
    def __init__(self):
        self.config = _load_config()
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate(self, topic: str, niche: str) -> dict:
        """Generate a full script for a given topic and niche."""
        niche_cfg = self.config["niches"].get(niche, self.config["niches"]["personal_finance"])
        target_length = niche_cfg["optimal_video_length_min"]
        target_words = int(target_length * 140)
        cpm = niche_cfg["avg_cpm"]
        sections = SECTION_TEMPLATES.get(niche, SECTION_TEMPLATES["personal_finance"])

        prompt = SCRIPT_TEMPLATE.format(
            niche=niche,
            topic=topic,
            target_length=target_length,
            target_words=target_words,
            cpm=cpm,
            s1=sections[0],
            s2=sections[1],
            s3=sections[2],
            s4=sections[3] if len(sections) > 3 else "Bonus Tips",
        )

        logger.info("Generating script for: %s", topic)
        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0]

        script_data = json.loads(raw)
        script_data["topic"] = topic
        script_data["niche"] = niche
        return script_data

    def save(self, script_data: dict, output_dir: str) -> str:
        """Save script to a .json file and a plain-text .txt file. Returns txt path."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = _slugify(script_data.get("title") or script_data["topic"])

        json_path = output_dir / f"{slug}.json"
        txt_path = output_dir / f"{slug}.txt"

        with open(json_path, "w") as f:
            json.dump(script_data, f, indent=2)

        with open(txt_path, "w") as f:
            f.write(script_data.get("full_script", ""))

        logger.info("Script saved: %s", txt_path)
        return str(txt_path)


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60]
