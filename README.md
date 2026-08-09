# text-to-png

A [Claude Code / Claude Skill](https://docs.claude.com/en/docs/claude-code/skills) that renders plain text, code snippets, terminal output, or ASCII art into a PNG image using a monospace font.

## What it does

- Renders any text to a PNG with correct monospace alignment (important for ASCII art and terminal output, which break under proportional fonts).
- Auto-discovers a monospace font already installed on your system (Consolas/Courier on Windows, Menlo/Monaco on macOS, DejaVu/Liberation Mono on Linux) — no bundled font required.
- Ships with four color themes (`default`, `terminal`, `dark`, `amber`) plus fully custom `--fg`/`--bg` colors.
- Auto-sizes the output image to fit the text exactly.

## Install

### As a Claude Skill

Download [`text-to-png.skill`](./text-to-png.skill) (or clone this repo) and either:
- drop the `.skill` file into Claude and click **Save skill**, or
- copy the `text-to-png/` folder into your `~/.claude/skills/` directory.

### Standalone (no Claude required)

The skill is just a Python script — you can use it directly:

```bash
pip install Pillow
python text-to-png/scripts/render_text_png.py --text "Hello, world!" --output hello.png
```

## Usage

```bash
# Plain text
python scripts/render_text_png.py --text "Hello, world!\nSecond line" --output out.png

# From a file (recommended for anything with meaningful whitespace, like ASCII art)
python scripts/render_text_png.py --file art.txt --output art.png

# Terminal theme with a custom font size
python scripts/render_text_png.py --file traceback.txt --output traceback.png --theme terminal --font-size 16

# Custom colors, transparent background
python scripts/render_text_png.py --text "BUILD PASSING" --fg "#00ff00" --bg "#000000" --output banner.png
```

### Options

| Flag | Description | Default |
|---|---|---|
| `--text` / `--file` | Text to render, or a path to a text file (mutually exclusive, one required) | — |
| `--output` | Output PNG path (required) | — |
| `--theme` | `default`, `terminal`, `dark`, or `amber` | `default` |
| `--fg`, `--bg` | Override theme colors (hex or CSS color name) | theme colors |
| `--font` | Path to a specific `.ttf`/`.ttc` font | auto-detected |
| `--font-size` | Font size in points | `20` |
| `--padding` | Padding in pixels around the text | `20` |
| `--line-spacing` | Line height multiplier | `1.0` |
| `--transparent` | Transparent background (ignores `--bg`) | off |

## License

MIT — see [LICENSE](./LICENSE).
