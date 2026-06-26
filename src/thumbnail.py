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

GRADIENT_PRESETS = [
    ("#0D1117", "#1a1a2e"),   # dark blue
    ("#1a0a00", "#3d1c02"),   # dark orange
    ("#000d1a", "#001a33"),   # navy
    ("#0a0a0a", "#1a1a1a"),   # near black
    ("#0d001a", "#1a0033"),   # dark purple
]

ACCENT_COLORS = ["#FFD700", "#FF4444", "#00CFFF", "#FF6B35", "#39FF14"]


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
            # Shadow
            draw.text((x + shadow_offset, y + shadow_offset), line, font=title_font, fill="#000000")
            # Main text
            color = accent if i == 0 else "#FFFFFF"
            draw.text((x, y), line, font=title_font, fill=color)

        # ── Stat / hook line ─────────────────────────────────────────────
        hook = _extract_hook(topic)
        if hook:
            hook_font = _get_font(52, bold=False)
            bbox = draw.textbbox((0, 0), hook, font=hook_font)
            tw = bbox[2] - bbox[0]
            x = (w - tw) // 2 + 50
            y = y_start + len(lines) * 130 + 30
            draw.text((x + 2, y + 2), hook, font=hook_font, fill="#000000")
            draw.text((x, y), hook, font=hook_font, fill="#CCCCCC")

        # ── Brand label (bottom right) ────────────────────────────────
        brand_font = _get_font(36, bold=True)
        brand = self.config.get("brand", "WealthFlow")
        draw.text((w - 220, h - 60), brand, font=brand_font, fill=accent)

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
