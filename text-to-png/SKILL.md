---
name: text-to-png
description: Turns text into a PNG image, two different ways. (1) Rasterize text/code/terminal output/ASCII art as-is into an image — use for "convert this ASCII art to a PNG", "make an image of this text", "screenshot this code snippet", "render this as a terminal-style image". (2) Redraw an ASCII box-and-arrow diagram as a real flowchart with clean rounded boxes and arrows — use for "turn this ASCII flowchart into a real diagram", "make this a proper flowchart image", or any ASCII diagram the user wants to look like an actual architecture/flow diagram rather than a screenshot of text. Use this whenever the deliverable is clearly meant to be an image file.
---

# Text to PNG

Two related but distinct capabilities live here — pick the right one:

| User wants... | Use |
|---|---|
| The text/art rendered exactly as typed, just as an image (code snippet, terminal output, ASCII art kept as ASCII) | `scripts/render_text_png.py` |
| An ASCII box-and-arrow diagram turned into an actual diagram — real rounded boxes, real arrows, not monospace characters | `scripts/render_flowchart.py` |

If in doubt: does the source use `+`, `-`, `|`, `v` to draw boxes and arrows meant to represent a *process/flow*? That's a flowchart request, not a literal-render request — use `render_flowchart.py`. If the ASCII is decorative (art, a diagram of literal shapes, a table) or the user just wants a picture of the text itself, use `render_text_png.py`.

## 1. Rasterizing text as-is (`render_text_png.py`)

The core problem this solves is alignment and font discovery: ASCII art and terminal output only look right in a genuine monospace font, and monospace fonts live in different places on different operating systems. The script handles that discovery instead of guessing at font paths inline.

```bash
python scripts/render_text_png.py --text "Hello, world!\nSecond line" --output out.png
```

Or from a file (preferred for anything more than a line or two, and required for ASCII art so whitespace/newlines survive exactly as given):

```bash
python scripts/render_text_png.py --file art.txt --output art.png
```

Options:
- **`--theme`**: `default` (black on white), `terminal` (green on near-black), `dark` (light gray on dark gray), `amber` (amber on near-black). Pick based on what the user describes — "terminal style" or "like a shell" → `terminal`; no styling mentioned → `default`.
- **`--fg` / `--bg`**: override theme colors directly (hex like `#00ff00` or CSS color names).
- **`--font-size`**: defaults to 20. Bump up (28-36) for short banner-style text; smaller (14-16) for dense code/log dumps.
- **`--font`**: path to a specific `.ttf`/`.ttc`. Otherwise auto-discovers a monospace font on the system (Consolas/Courier on Windows, Menlo/Monaco on macOS, DejaVu/Liberation Mono on Linux), falling back to PIL's bitmap font with a warning if none is found — mention that to the user if it happens, since the fallback is lower quality.
- **`--transparent`**: transparent background instead of solid. Ignores `--bg`.
- **`--padding`**, **`--line-spacing`**: margin and line-height tuning.

Image size is always computed automatically from the text — no need to guess dimensions.

**Workflow**: get the text into a file if it's more than a line or two or has meaningful whitespace (`--text` requires literal `\n` escapes and is easy to mangle) → pick theme/size → run → check the output before calling it done (a bitmap-fallback warning is worth flagging).

## 2. Redrawing an ASCII diagram as a real flowchart (`render_flowchart.py`)

Takes a JSON description of the diagram's structure (not the raw ASCII) and draws it with proper rounded boxes, wrapped/bulleted text, and arrows — including fan-out (one box splitting into several) and fan-in (several boxes merging back into one). You do the reading of the ASCII diagram yourself (you're good at this — treat it like interpreting a hand-drawn flowchart) and translate it into the JSON spec; the script only handles layout and drawing.

```bash
python scripts/render_flowchart.py --spec spec.json --output flowchart.png
```

(`--spec-json '<inline JSON>'` also works for short specs.)

### Spec format

```json
{
  "rows": [
    {"nodes": [{"type": "plain", "lines": ["New user message"]}]},
    {"nodes": [{"type": "box", "title": "Retrieval layer", "bullets": ["fact one", "fact two"]}]},
    {"label": "delegates to one or more workers", "nodes": [
        {"type": "box", "title": "worker A", "subtitle": "(own guardrail)"},
        {"type": "box", "title": "worker B", "subtitle": "(own guardrail)"}
    ]},
    {"label": "results assembled", "nodes": [{"type": "box", "title": "done"}]}
  ]
}
```

- Rows are drawn top to bottom, connected by arrows automatically.
- A row's `"label"` annotates the arrow(s) leading INTO that row — use it for the parenthetical/side notes that appear next to arrows in the source ASCII (e.g. "at end of session, not per turn").
- **`"nodes"`**: one node per row draws a single centered box/line with a straight arrow in and out. Multiple nodes in a row auto fan-out (if the previous row had one node) or fan-in (if the next row has one node) — this is what handles branching diagrams like an orchestrator delegating to parallel workers.
- Node type `"plain"`: borderless bold centered text — use for start/end labels and inline steps that aren't boxed in the source (`"lines"`: list of strings, one per line).
- Node type `"box"`: a rounded rectangle with a bold `"title"`, plus EITHER `"subtitle"` (one centered regular-weight line, for simple two-line boxes) OR `"bullets"` (a left-aligned, word-wrapped list, for boxes with several sub-points) — not both.

### Workflow

1. Read the ASCII diagram and identify: the linear sequence of steps, which boxes have bullet lists vs. simple labels, where branching happens (one node's arrow splits into several, or several arrows merge into one), and any side-annotations on arrows.
2. Translate that structure into the JSON spec — this is an interpretation step, not a text transcription, so use your judgment on how to group bullets or word a title if the ASCII is terse.
3. Run the script, check the output image, and adjust the spec (not the script) if spacing/wrapping looks off for unusually long titles or many bullets.
