"""YouTube script generator — works with Groq (free), Gemini (free), or Claude."""

import json
import logging
from pathlib import Path

import yaml
from .llm import chat, parse_json

logger = logging.getLogger(__name__)


def _load_config():
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


SYSTEM_PROMPT = """\
You are a world-class YouTube scriptwriter for faceless educational channels.
Write hooks that stop the scroll, deliver dense value, and always end with a subscribe CTA.
Use "you" and "we" — never "I". Speak to the viewer's desire for transformation.
"""

# Call 1: metadata only — small JSON, no long text fields (avoids newline-in-JSON bug)
META_PROMPT = """\
Topic: "{topic}" | Niche: {niche} | Target: {target_length} min

Return ONLY this JSON (no extra text, no markdown fences):
{{"title":"...","hook_line":"...","key_takeaways":["...","...","..."],"section_names":["{s1}","{s2}","{s3}","{s4}"],"estimated_duration_min":{target_length}}}
"""

# Call 2: full script as plain text — no JSON at all
SCRIPT_PROMPT = """\
Write a complete word-for-word YouTube script for a faceless {niche} channel.

Topic: "{topic}"
Target: {target_length} minutes (~{target_words} words)

Use this exact structure with these headers on their own lines:

[HOOK]
[INTRO]
[{s1}]
[{s2}]
[{s3}]
[{s4}]
[RECAP & CTA]

Write the full script now. Plain text only — no JSON, no markdown.
"""

SECTION_TEMPLATES: dict[str, list[str]] = {
    "personal_finance": [
        "The Problem Nobody Talks About",
        "The Strategy That Actually Works",
        "Step-by-Step Implementation",
        "Common Mistakes to Avoid",
    ],
    "ai_tech": [
        "Why This Changes Everything",
        "How It Actually Works",
        "Practical Use Cases",
        "What Comes Next",
    ],
    "business": [
        "The Opportunity Nobody Sees",
        "The Blueprint",
        "Getting Your First Win",
        "Scaling Up",
    ],
    "health": [
        "The Science Behind It",
        "What Most People Get Wrong",
        "The Protocol That Works",
        "Sustainable Long-Term Habits",
    ],
}


class ScriptGenerator:
    def __init__(self):
        self.config = _load_config()

    def _params(self, niche: str):
        niche_cfg = self.config["niches"].get(niche, self.config["niches"]["personal_finance"])
        target_length = niche_cfg["optimal_video_length_min"]
        target_words  = int(target_length * 140)
        sections      = SECTION_TEMPLATES.get(niche, SECTION_TEMPLATES["personal_finance"])
        return target_length, target_words, sections

    def generate_meta(self, topic: str, niche: str) -> dict:
        """Call 1: small metadata JSON only (~3s)."""
        target_length, _, sections = self._params(niche)
        s1, s2, s3, s4 = sections
        meta_raw = chat(SYSTEM_PROMPT, META_PROMPT.format(
            topic=topic, niche=niche, target_length=target_length,
            s1=s1, s2=s2, s3=s3, s4=s4,
        ), max_tokens=512)
        try:
            return parse_json(meta_raw)
        except Exception as e:
            logger.warning("Metadata parse failed (%s), using defaults", e)
            return {"title": topic, "hook_line": "", "key_takeaways": [],
                    "section_names": sections, "estimated_duration_min": target_length}

    def generate_script_text(self, topic: str, niche: str) -> str:
        """Call 2: full plain-text script only (~20s)."""
        target_length, target_words, sections = self._params(niche)
        s1, s2, s3, s4 = sections
        logger.info("Generating full script for: %s", topic)
        return chat(SYSTEM_PROMPT, SCRIPT_PROMPT.format(
            topic=topic, niche=niche, target_length=target_length,
            target_words=target_words, s1=s1, s2=s2, s3=s3, s4=s4,
        ), max_tokens=4096)

    def build_result(self, meta: dict, full_script: str, topic: str, niche: str) -> dict:
        """Assemble final script dict from separate meta + script text."""
        target_length, _, sections = self._params(niche)
        section_objects = _parse_sections(full_script, meta.get("section_names", sections))
        return {
            "topic": topic, "niche": niche,
            "title": meta.get("title", topic),
            "hook_line": meta.get("hook_line", ""),
            "key_takeaways": meta.get("key_takeaways", []),
            "estimated_duration_min": meta.get("estimated_duration_min", target_length),
            "word_count": len(full_script.split()),
            "sections": section_objects,
            "full_script": full_script,
        }

    def generate(self, topic: str, niche: str) -> dict:
        """All-in-one (sequential). Use generate_meta/generate_script_text for parallelism."""
        meta = self.generate_meta(topic, niche)
        full_script = self.generate_script_text(topic, niche)
        return self.build_result(meta, full_script, topic, niche)

    def save(self, script_data: dict, output_dir: str) -> str:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = _slugify(script_data.get("title") or script_data["topic"])
        txt_path = output_dir / f"{slug}.txt"
        with open(txt_path, "w") as f:
            f.write(script_data.get("full_script", ""))
        logger.info("Script saved: %s", txt_path)
        return str(txt_path)


def _parse_sections(script: str, section_names: list[str]) -> list[dict]:
    """Split the plain-text script into section dicts by [HEADER] markers."""
    import re
    parts = re.split(r"\[([^\]]+)\]", script)
    sections = []
    # parts alternates: text_before, header, content, header, content ...
    for i in range(1, len(parts) - 1, 2):
        header  = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections.append({
            "name":         header,
            "content":      content,
            "duration_sec": max(int(len(content.split()) / 140 * 60), 30),
        })
    return sections if sections else [{"name": n, "content": "", "duration_sec": 120} for n in section_names]


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60]
