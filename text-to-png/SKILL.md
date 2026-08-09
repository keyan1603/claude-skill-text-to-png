---
name: text-to-png
description: Render plain text, code snippets, terminal output, or ASCII art into a PNG image using a monospace font. Use this whenever the user wants text turned into an image file — e.g. "convert this ASCII art to a PNG", "make an image of this text", "screenshot this code snippet without a screenshot tool", "render this as a terminal-style image", or "I need this banner/art as a picture I can paste into Slack/docs/a README". Also use it if the user asks for a quick text-as-image render even without naming a format, as long as the deliverable is clearly an image file rather than a document.
---

# Text to PNG

Renders text (plain prose, code, terminal transcripts, or ASCII art) into a PNG image. The core problem this solves is alignment and font discovery: ASCII art and terminal output only look right in a genuine monospace font, and monospace fonts live in different places on different operating systems. The bundled script handles that discovery for you instead of guessing at font paths inline.

## Quick start

```bash
python scripts/render_text_png.py --text "Hello, world!\nSecond line" --output out.png
```

Or from a file (preferred for anything more than a line or two, and required for ASCII art so whitespace/newlines survive exactly as given):

```bash
python scripts/render_text_png.py --file art.txt --output art.png
```

Requires Pillow (`pip install Pillow` if not already available — check first with `python -c "import PIL"` before installing).

## Choosing options

- **`--theme`**: `default` (black on white), `terminal` (green on near-black), `dark` (light gray on dark gray), `amber` (amber on near-black). Pick based on what the user describes — "terminal style" or "like a shell" → `terminal`; no styling mentioned → `default`.
- **`--fg` / `--bg`**: override theme colors directly (hex like `#00ff00` or CSS color names). Use when the user names specific colors instead of a vibe.
- **`--font-size`**: defaults to 20. Bump it up (28-36) for short banner-style text or ASCII art the user wants to look bold; keep it smaller (14-16) for dense code/log dumps so lines don't run too wide.
- **`--font`**: path to a specific `.ttf`/`.ttc` if the user wants a particular typeface. Otherwise the script auto-discovers a monospace font already installed on the system (Consolas/Courier on Windows, Menlo/Monaco on macOS, DejaVu/Liberation Mono on Linux). If none is found it falls back to PIL's built-in bitmap font and prints a warning — mention this to the user if it happens, since the bitmap fallback is lower quality and worth calling out.
- **`--transparent`**: transparent background instead of a solid one — good for logos/banners meant to sit on top of other content. Ignores `--bg` when set.
- **`--padding`**: pixels of margin around the text block (default 20).
- **`--line-spacing`**: multiplier on line height (default 1.0) if lines look too cramped or too loose.

The image is always sized automatically to fit the text exactly (longest line × character width, number of lines × line height, plus padding) — no need to guess dimensions.

## Workflow

1. Get the text. If it's more than ~1-2 lines, or contains meaningful whitespace/alignment (ASCII art, tables, indented code), write it to a temp file and use `--file` rather than `--text`, so newlines and spacing come through exactly — `--text` requires literal `\n` escapes and is easy to mangle for anything nontrivial.
2. Pick theme/colors/font-size based on what the user asked for (see above).
3. Run the script, pointing `--output` at a sensible path (ask the user or infer from context if not specified).
4. Open/check the resulting PNG before telling the user it's done — dimensions or a quick visual check catch cases like an unexpectedly-found bitmap-font fallback.
