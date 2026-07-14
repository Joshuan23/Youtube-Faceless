"""Trending topic discovery for each niche."""

import random
import logging
from datetime import datetime

import yaml
from .llm import chat, parse_json, active_provider

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
    "nursery_rhymes": [
        "Twinkle Twinkle Little Star",
        "The Wheels on the Bus",
        "Old MacDonald Had a Farm",
        "Baby Shark dance song",
        "Row Row Row Your Boat",
        "Five Little Ducks went out one day",
        "If You're Happy and You Know It",
        "Head Shoulders Knees and Toes",
        "The Itsy Bitsy Spider",
        "Rain Rain Go Away",
        "Five Little Monkeys jumping on the bed",
        "Mary Had a Little Lamb",
        "Hickory Dickory Dock",
        "Humpty Dumpty sat on a wall",
        "This Little Piggy went to market",
        "Ring Around the Rosie",
        "Little Bo Peep",
        "Jack and Jill went up the hill",
        "The Farmer in the Dell",
        "Bingo the dog song",
    ],
    "lullabies": [
        "Hush Little Baby lullaby",
        "Rock-a-bye Baby bedtime song",
        "Twinkle Twinkle sleepy version",
        "gentle counting sheep lullaby",
        "Brahms Lullaby for babies",
        "goodnight moon bedtime song",
        "soft rainfall sleepy song",
        "sweet dreams little one lullaby",
        "starlight bedtime lullaby",
        "cozy blanket sleepy song",
    ],
    "learning_songs": [
        "ABC Alphabet Song for kids",
        "Counting 1 to 10 song",
        "Colors of the Rainbow song",
        "Days of the Week song",
        "Shapes song for toddlers",
        "animal sounds learning song",
        "numbers 1 to 20 counting song",
        "please and thank you manners song",
        "brushing teeth song for toddlers",
        "clean up tidy time song",
    ],
}


def get_trending_topics(niche: str, count: int = 5) -> list[str]:
    """
    Returns a list of nursery-rhyme/song ideas for the given style.
    Tries an LLM for fresh ideas; falls back to the local seed list.
    """
    topics = _claude_topic_ideas(niche, count)
    if topics:
        return topics
    seed = list(SEED_TOPICS.get(niche) or next(iter(SEED_TOPICS.values())))
    random.shuffle(seed)
    return seed[:count]


def _claude_topic_ideas(niche: str, count: int) -> list[str]:
    if active_provider() == "none":
        return []
    try:
        raw = chat(
            "You brainstorm ideas for a children's nursery rhyme YouTube channel. Return only valid JSON.",
            (
                f"Suggest {count} sing-along song ideas for a kids '{niche}' channel (ages 1-5).\n"
                "Requirements:\n"
                "- Each idea is a short, friendly, searchable song title\n"
                "- Mix beloved classics with fresh, wholesome themes (animals, colors, counting, bedtime)\n"
                "- Absolutely nothing scary, violent, or inappropriate for toddlers\n\n"
                "Return ONLY a JSON array of strings, no explanation."
            ),
            max_tokens=512,
        )
        return parse_json(raw)
    except Exception as e:
        logger.warning("LLM topic generation failed: %s", e)
        return []
