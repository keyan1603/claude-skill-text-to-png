#!/usr/bin/env python3
"""Render plain text or ASCII art into a PNG image using a monospace font.

Usage:
    python render_text_png.py --text "hello\nworld" --output out.png
    python render_text_png.py --file input.txt --output out.png --theme terminal
    python render_text_png.py --file art.txt --output art.png --fg "#00ff00" --bg "#000000" --font-size 24
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print(
        "Pillow is required. Install it with: pip install Pillow",
        file=sys.stderr,
    )
    sys.exit(1)

THEMES = {
    "default": {"fg": "#000000", "bg": "#ffffff"},
    "terminal": {"fg": "#33ff33", "bg": "#0c0c0c"},
    "dark": {"fg": "#e6e6e6", "bg": "#1e1e1e"},
    "amber": {"fg": "#ffb000", "bg": "#1a1000"},
}

# Common monospace font locations across platforms, tried in order.
# A real monospace font keeps ASCII art aligned; PIL's bitmap default font
# does not, so we only fall back to it if nothing else is found.
CANDIDATE_FONTS = [
    # Windows
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\cour.ttf",
    r"C:\Windows\Fonts\lucon.ttf",
    # macOS
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/Library/Fonts/Courier New.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
]


def find_monospace_font(explicit_path: str | None, size: int) -> tuple[ImageFont.FreeTypeFont, bool]:
    """Return (font, is_scalable). Tries explicit path, then known system fonts."""
    candidates = ([explicit_path] if explicit_path else []) + CANDIDATE_FONTS
    for path in candidates:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size), True
            except OSError:
                continue
    # Last resort: PIL's built-in bitmap font (fixed size, always available).
    print(
        "Warning: no monospace TTF font found on this system; falling back to "
        "PIL's built-in bitmap font. Pass --font <path-to-ttf> for better results.",
        file=sys.stderr,
    )
    return ImageFont.load_default(), False


def render(
    text: str,
    output: Path,
    fg: str,
    bg: str,
    font_path: str | None,
    font_size: int,
    padding: int,
    line_spacing: float,
    transparent: bool,
) -> None:
    text = text.replace("\t", "    ")
    lines = text.splitlines() or [""]

    font, is_scalable = find_monospace_font(font_path, font_size)

    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    if is_scalable:
        char_bbox = draw.textbbox((0, 0), "M", font=font)
        char_width = char_bbox[2] - char_bbox[0]
        ascent, descent = font.getmetrics()
        line_height = int((ascent + descent) * line_spacing)
    else:
        char_bbox = draw.textbbox((0, 0), "M", font=font)
        char_width = char_bbox[2] - char_bbox[0] or 6
        line_height = int((char_bbox[3] - char_bbox[1] + 4) * line_spacing)

    max_line_len = max((len(line) for line in lines), default=0)
    img_width = max(char_width * max_line_len + padding * 2, 1)
    img_height = max(line_height * len(lines) + padding * 2, 1)

    mode = "RGBA" if transparent else "RGB"
    bg_color = (0, 0, 0, 0) if transparent else bg

    img = Image.new(mode, (img_width, img_height), bg_color)
    draw = ImageDraw.Draw(img)

    y = padding
    for line in lines:
        draw.text((padding, y), line, font=font, fill=fg)
        y += line_height

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output)
    print(f"Saved {img_width}x{img_height} image to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Text to render (use \\n for newlines)")
    src.add_argument("--file", help="Path to a text file to render")

    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--theme", choices=THEMES.keys(), default="default", help="Preset color theme")
    parser.add_argument("--fg", help="Foreground (text) color, overrides theme, e.g. '#00ff00' or 'green'")
    parser.add_argument("--bg", help="Background color, overrides theme")
    parser.add_argument("--font", help="Path to a .ttf/.ttc font file")
    parser.add_argument("--font-size", type=int, default=20, help="Font size in points (default: 20)")
    parser.add_argument("--padding", type=int, default=20, help="Padding in pixels around the text (default: 20)")
    parser.add_argument("--line-spacing", type=float, default=1.0, help="Line height multiplier (default: 1.0)")
    parser.add_argument("--transparent", action="store_true", help="Transparent background (ignores --bg)")

    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.text.replace("\\n", "\n")

    theme = THEMES[args.theme]
    fg = args.fg or theme["fg"]
    bg = args.bg or theme["bg"]

    render(
        text=text,
        output=Path(args.output),
        fg=fg,
        bg=bg,
        font_path=args.font,
        font_size=args.font_size,
        padding=args.padding,
        line_spacing=args.line_spacing,
        transparent=args.transparent,
    )


if __name__ == "__main__":
    main()
