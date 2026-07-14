"""High-CTR YouTube thumbnail generator using Pillow."""

import os
import textwrap
import logging
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "thumbnails"

# Bright, cheerful kid-friendly gradients (light → slightly deeper same hue)
GRADIENT_PRESETS = [
    ("#8FD3FF", "#3FA9F5"),   # sky blue
    ("#FFD3E8", "#FF7EB6"),   # bubblegum pink
    ("#FFF3B0", "#FFD24C"),   # sunny yellow
    ("#C8F7C5", "#5FD068"),   # meadow green
    ("#E3D0FF", "#B292FF"),   # lavender
]

ACCENT_COLORS = ["#FFEB3B", "#FF5FA2", "#FF7F27", "#4CD964", "#9C5CFF"]


def _load_config():
    p = Path(__file__).parent.parent / "config.yaml"
    with open(p) as f:
        return yaml.safe_load(f)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []
    if bold:
        candidates = [
            FONTS_DIR / "DejaVuSans-Bold.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
        ]
    else:
        candidates = [
            FONTS_DIR / "DejaVuSans.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
        ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_gradient_bg(img: Image.Image, w: int, h: int, color1: str, color2: str):
    c1 = tuple(int(color1.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    c2 = tuple(int(color2.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    # 1×2 image resized to full size — PIL does this in C, no Python loop
    grad = Image.new("RGB", (1, 2))
    grad.putpixel((0, 0), c1)
    grad.putpixel((0, 1), c2)
    img.paste(grad.resize((w, h), Image.BILINEAR))


class ThumbnailCreator:
    def __init__(self):
        self.config = _load_config()["thumbnail"]

    def create(self, title: str, topic: str, output_path: str, variant: int = 0) -> str:
        """
        Generate a YouTube thumbnail.
        variant: 0-4 for different color scheme presets
        """
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        w, h = self.config["width"], self.config["height"]
        img = Image.new("RGB", (w, h))

        # Gradient background — fast PIL resize, no Python loop
        g1, g2 = GRADIENT_PRESETS[variant % len(GRADIENT_PRESETS)]
        _draw_gradient_bg(img, w, h, g1, g2)
        draw = ImageDraw.Draw(img)

        # Bold accent border stripe at top
        accent = ACCENT_COLORS[variant % len(ACCENT_COLORS)]
        border_w = self.config["border_width"]
        draw.rectangle([(0, 0), (w, border_w)], fill=accent)
        draw.rectangle([(0, h - border_w), (w, h)], fill=accent)

        # LEFT accent bar
        draw.rectangle([(0, 0), (border_w, h)], fill=accent)

        # ── Main title text ──────────────────────────────────────────────
        lines = textwrap.wrap(title.upper(), width=18)[:3]
        y_start = h // 6
        title_font = _get_font(112, bold=True)
        shadow_offset = 4

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=title_font)
            tw = bbox[2] - bbox[0]
            x = (w - tw) // 2 + 50  # slight right offset for visual weight
            y = y_start + i * 130
            # Shadow / outline for contrast on bright backgrounds
            draw.text((x + shadow_offset, y + shadow_offset), line, font=title_font, fill="#0B2545")
            # Main text — first line pops in accent, rest in deep navy for readability
            color = accent if i == 0 else "#0B2545"
            draw.text((x, y), line, font=title_font, fill=color)

        # ── Stat / hook line ─────────────────────────────────────────────
        hook = _extract_hook(topic)
        if hook:
            hook_font = _get_font(52, bold=False)
            bbox = draw.textbbox((0, 0), hook, font=hook_font)
            tw = bbox[2] - bbox[0]
            x = (w - tw) // 2 + 50
            y = y_start + len(lines) * 130 + 30
            draw.text((x + 2, y + 2), hook, font=hook_font, fill="#FFFFFF")
            draw.text((x, y), hook, font=hook_font, fill="#0B2545")

        # ── Brand label (bottom right) ────────────────────────────────
        brand_font = _get_font(40, bold=True)
        brand = self.config.get("brand", "Twinkle Tots")
        bb = draw.textbbox((0, 0), brand, font=brand_font)
        bw = bb[2] - bb[0]
        bx, by = w - bw - 40, h - 64
        draw.text((bx + 2, by + 2), brand, font=brand_font, fill="#FFFFFF")
        draw.text((bx, by), brand, font=brand_font, fill="#0B2545")

        img.save(output_path, "JPEG", quality=95)
        logger.info("Thumbnail saved: %s", output_path)
        return output_path

    def create_ab_set(self, title: str, topic: str, output_dir: str) -> list[str]:
        """Generate 3 thumbnail variants for A/B testing."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(3):
            slug = _slugify(title)
            p = str(output_dir / f"{slug}_thumb_v{i + 1}.jpg")
            paths.append(self.create(title, topic, p, variant=i))
        return paths


def _extract_hook(topic: str) -> str:
    """Pull out a numeric or power-word hook from the topic."""
    import re
    match = re.search(r"\$[\d,]+|\d+[k%]?|\d+ ways|\d+ steps|\d+ secrets", topic, re.I)
    if match:
        return match.group(0).upper()
    keywords = ["secret", "truth", "hidden", "never", "always", "revealed"]
    for kw in keywords:
        if kw in topic.lower():
            return kw.upper()
    return ""


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50]
