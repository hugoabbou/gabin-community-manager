import os
import uuid
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
import numpy as np

_base = os.getenv("DATA_DIR", os.path.dirname(os.path.dirname(__file__)))
GENERATED_DIR = os.path.join(_base, "generated")
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
LIBRARY_DIR = os.path.join(_base, "library")

LIBRARY_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Gabin brand colors
COLOR_BG = (13, 13, 13)          # #0D0D0D
COLOR_BG2 = (26, 18, 12)         # slightly warm dark
COLOR_GOLD = (212, 165, 116)      # #D4A574
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (140, 130, 120)
COLOR_RED = (160, 40, 40)

STORY_W, STORY_H = 1080, 1920

SPORT_COLORS = {
    "Football": (212, 165, 116),
    "Soccer": (212, 165, 116),
    "Tennis": (100, 180, 80),
    "Basketball": (220, 100, 30),
    "Rugby": (80, 120, 200),
}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def get_library_images() -> list:
    """Return all images in the visual library."""
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    images = []
    for f in sorted(os.listdir(LIBRARY_DIR)):
        if os.path.splitext(f)[1].lower() in LIBRARY_EXTENSIONS:
            images.append({
                "filename": f,
                "url": f"assets/library/{f}",
                "path": os.path.join(LIBRARY_DIR, f),
            })
    return images


def _pick_library_bg(themes: list = None) -> Optional[Image.Image]:
    """Pick a random image from the library to use as background."""
    import random
    images = get_library_images()
    if not images:
        return None
    chosen = random.choice(images)
    img = Image.open(chosen["path"]).convert("RGB")
    img = img.resize((STORY_W, STORY_H), Image.LANCZOS)
    # Dark overlay so text remains readable
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 185))
    result = img.convert("RGBA")
    result = Image.alpha_composite(result, overlay)
    return result.convert("RGB")


def _gradient_bg(width: int, height: int) -> Image.Image:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for ch in range(3):
        arr[:, :, ch] = np.linspace(COLOR_BG[ch], COLOR_BG2[ch], height)[:, np.newaxis]
    return Image.fromarray(arr, "RGB")


def _draw_logo(draw: ImageDraw.ImageDraw, img: Image.Image, x: int, y: int, size: int = 100):
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((size, size), Image.LANCZOS)
        # Circular mask
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        bg = Image.new("RGB", (size, size), COLOR_BG)
        bg.paste(logo, (0, 0), mask)
        img.paste(bg, (x, y))
    else:
        # Placeholder: draw a stylized "G" in a circle
        draw.ellipse((x, y, x + size, y + size), outline=COLOR_GOLD, width=3)
        font = _load_font(int(size * 0.55), bold=True)
        draw.text((x + size // 2, y + size // 2), "g", font=font,
                  fill=COLOR_GOLD, anchor="mm")


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_centered_text(draw, text, font, y, color, max_width, line_spacing=8):
    lines = _wrap_text(text, font, max_width, draw)
    total_h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        total_h += (bbox[3] - bbox[1]) + line_spacing
    cy = y
    for line in lines:
        draw.text((STORY_W // 2, cy), line, font=font, fill=color, anchor="mt")
        bbox = draw.textbbox((0, 0), line, font=font)
        cy += (bbox[3] - bbox[1]) + line_spacing
    return cy


def create_story_image(
    title: str,
    subtitle: str = "",
    body: str = "",
    cta: str = "",
    hashtags: list = None,
    sport_event: dict = None,
    themes: list = None,
) -> str:
    if hashtags is None:
        hashtags = []
    if themes is None:
        themes = []

    is_sport = sport_event is not None or "sports_event" in (themes or [])
    sport_name = sport_event.get("sport", "Football") if sport_event else "Football"
    accent_color = SPORT_COLORS.get(sport_name, COLOR_GOLD) if is_sport else COLOR_GOLD

    library_img = _pick_library_bg(themes)
    img = library_img if library_img is not None else _gradient_bg(STORY_W, STORY_H)
    draw = ImageDraw.Draw(img)

    # --- Top bar (accent line) ---
    draw.rectangle((0, 0, STORY_W, 8), fill=accent_color)

    # --- Logo ---
    _draw_logo(draw, img, 60, 50, 90)

    # --- "CHEZ GABIN" label ---
    label_font = _load_font(28)
    draw.text((STORY_W - 60, 90), "@gabinrestaurant", font=label_font,
              fill=COLOR_GRAY, anchor="rm")

    # --- Sport emoji (big) ---
    if sport_event:
        emoji = sport_event.get("emoji", "🏆")
        emoji_font = _load_font(120)
        draw.text((STORY_W // 2, 300), emoji, font=emoji_font, fill=COLOR_WHITE, anchor="mm")

    # --- Main Title ---
    title_y = 460 if sport_event else 380
    title_font = _load_font(88, bold=True)
    title_lines = _wrap_text(title.upper() if is_sport else title, title_font, STORY_W - 120, draw)

    cy = title_y
    for line in title_lines:
        draw.text((STORY_W // 2, cy), line, font=title_font, fill=COLOR_WHITE, anchor="mt")
        bbox = draw.textbbox((0, 0), line, font=title_font)
        cy += (bbox[3] - bbox[1]) + 12

    # --- Accent line under title ---
    line_y = cy + 20
    draw.rectangle((STORY_W // 2 - 60, line_y, STORY_W // 2 + 60, line_y + 4), fill=accent_color)
    cy = line_y + 32

    # --- Subtitle (date/time or dish name) ---
    if subtitle:
        sub_font = _load_font(48)
        cy = _draw_centered_text(draw, subtitle, sub_font, cy, accent_color, STORY_W - 160)
        cy += 20

    # --- Sport event detail ---
    if sport_event:
        detail_font = _load_font(38)
        league = sport_event.get("league", "")
        date_time = f"{sport_event.get('date_display', '')} à {sport_event.get('time_display', '')}".strip(" à")
        if league:
            cy = _draw_centered_text(draw, league, detail_font, cy, COLOR_GRAY, STORY_W - 160)
            cy += 8
        if date_time:
            cy = _draw_centered_text(draw, date_time, detail_font, cy, COLOR_GRAY, STORY_W - 160)
            cy += 20

    # --- Divider ---
    mid_y = max(cy + 40, STORY_H - 680)
    draw.rectangle((80, mid_y, STORY_W - 80, mid_y + 1), fill=(50, 45, 40))

    # --- Body text ---
    body_font = _load_font(42)
    body_y = mid_y + 40
    if body:
        body_y = _draw_centered_text(draw, body, body_font, body_y, COLOR_WHITE, STORY_W - 160, line_spacing=14)
        body_y += 30

    # --- CTA ---
    if cta:
        cta_font = _load_font(46, bold=True)
        cta_y = max(body_y + 20, STORY_H - 360)
        # CTA background pill
        cta_bbox = draw.textbbox((0, 0), cta, font=cta_font)
        cta_w = cta_bbox[2] - cta_bbox[0] + 80
        cta_h = cta_bbox[3] - cta_bbox[1] + 30
        cta_x = (STORY_W - cta_w) // 2
        draw.rounded_rectangle(
            (cta_x, cta_y, cta_x + cta_w, cta_y + cta_h),
            radius=30,
            fill=accent_color,
        )
        draw.text((STORY_W // 2, cta_y + cta_h // 2), cta, font=cta_font,
                  fill=COLOR_BG, anchor="mm")

    # --- Hashtags ---
    if hashtags:
        tag_text = " ".join(f"#{h}" for h in hashtags[:6])
        tag_font = _load_font(26)
        draw.text((STORY_W // 2, STORY_H - 80), tag_text, font=tag_font,
                  fill=COLOR_GRAY, anchor="mm")

    # --- Bottom accent bar ---
    draw.rectangle((0, STORY_H - 8, STORY_W, STORY_H), fill=accent_color)

    # Save
    os.makedirs(GENERATED_DIR, exist_ok=True)
    filename = f"story_{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(GENERATED_DIR, filename)
    img.save(path, "PNG", quality=95)
    return f"generated/{filename}"
