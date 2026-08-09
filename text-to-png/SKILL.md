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

Takes a JSON description of the diagram's structure (not the raw ASCII) and draws it with proper rounded boxes, wrapped/bulleted text, and arrows — including fan-out/fan-in that reconverges (one box splitting into several that later merge back into a shared next step) AND branches that never reconverge (e.g. a guardrail that either terminates the flow right there or continues down a completely different, longer path). You do the reading of the ASCII diagram yourself (you're good at this — treat it like interpreting a hand-drawn flowchart) and translate it into the JSON spec; the script only handles layout and drawing.

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
- **`"nodes"`**: one node per row draws a single centered box/line with a straight arrow in and out. Multiple nodes in a row auto fan-out (if the previous row had one node) or fan-in (if the next row has one node) — this is what handles branching diagrams like an orchestrator delegating to parallel workers, where every branch reconverges on the same next step.
- Node type `"plain"`: borderless centered text, in one of two forms — `"lines"` (a list of strings, all rendered bold, for short labels like a start/end node) OR `"title"` + optional `"detail"` (a bold title with smaller regular-weight description lines under it, for an unboxed process step that still needs explanatory subtext, like "Retrieval (span: retrieval)" style steps that aren't drawn as boxes in the source).
- Node type `"box"`: a rounded rectangle with a bold `"title"`, plus AT MOST ONE of: `"subtitle"` (one centered regular-weight line, for simple two-line boxes), `"bullets"` (a left-aligned, word-wrapped bullet list, for boxes with several distinct sub-points), or `"paragraph"` (a left-aligned, word-wrapped block of plain text with no bullet marker, for a single descriptive blurb under the title).
- **`"title"` can be a string or a list of strings** on both node types. Match how the source ASCII actually wraps it — if the source splits a long name across two lines (often done specifically to keep that box narrow), pass `"title": ["line one", "line two"]` rather than joining it into one long line. This matters more than it sounds: an unexpectedly wide box shifts that node's connector anchor point sideways, which can visibly misalign arrows coming from or going to neighboring rows — always match the source's line breaks for titles, not just for bullets/paragraphs.

### Horizontal chains

Some diagrams flow left-to-right instead of top-to-bottom (a pipeline: `A --> B --> C`). Use `{"type": "hchain", "nodes": [...]}` as a row entry — nodes are laid out side by side connected by rightward arrows, instead of the usual vertical stacking:

```json
{"type": "hchain", "nodes": [
    {"type": "plain", "title": "Traced requests", "detail": ["(structured JSON)"]},
    {"type": "plain", "title": "S3 / Blob Storage", "detail": ["(durable, append-only)"]}
]}
```

An hchain row still connects vertically to whatever comes before/after it in the same way a normal row would — the incoming arrow lands on the flow's first node, and any outgoing arrow leaves from the flow's last node.

For a "snake" layout (a pipeline that reverses direction every row to stay compact — common when there isn't room to keep going straight down), add `"direction": "left"` to make that row flow right-to-left instead: `"nodes"` stays in flow order (first = upstream, last = downstream), only the visual placement and arrowheads flip. This is what makes the incoming/outgoing vertical connectors line up correctly between rows — the entry/exit anchor is always the flow-first/flow-last node's position, never "whichever node is on the left," so a row above ending on the right and a reversed row below starting on the right will connect straight down without extra work.

### Branches that don't reconverge

For a decision point where the paths genuinely diverge — one side terminates, the other continues on a different, unrelated path (guardrail blocked/safe, validation pass/fail, error handling) — use a `"branch"` entry instead of a multi-node row. It MUST be the last entry in whatever `"rows"` list it appears in (nothing reconverges after it), and each branch's own `"rows"` follows the same rules recursively, so a branch can end in another branch:

```json
{"type": "branch", "branches": [
    {"label": "blocked", "rows": [
        {"nodes": [{"type": "plain", "lines": ["Trace ends here", "(1 span total)"]}]}
    ]},
    {"label": "safe", "rows": [
        {"nodes": [{"type": "plain", "lines": ["Retrieval"]}]},
        {"nodes": [{"type": "plain", "lines": ["Generation"]}]}
    ]}
]}
```

Each branch's `"label"` is drawn beside its own arrow right after the split (matching how ASCII diagrams usually annotate branches), not centered on a shared bar. Branch columns can be different lengths — one ending immediately while another continues for several more rows — and are otherwise laid out exactly like a top-level diagram.

Rule of thumb for which shape to use: if every path in the ASCII eventually funnels back into the same box, it's a fan-out/fan-in `"nodes"` row. If the ASCII shows some paths ending (a terminal label, a dead end) while others keep going, it's a non-reconverging `"branch"`.

### Workflow

1. Read the ASCII diagram and identify: the linear sequence of steps, which boxes have bullet/paragraph bodies vs. simple labels, where branching happens and whether it reconverges or not, and any side-annotations on arrows.
2. Translate that structure into the JSON spec — this is an interpretation step, not a text transcription, so use your judgment on how to group bullets or word a title if the ASCII is terse.
3. Run the script, check the output image, and adjust the spec (not the script) if spacing/wrapping looks off for unusually long titles or many bullets. If an arrow lands in the wrong place relative to a node, check whether that node's title matches the source's own line-wrapping (see above) before assuming it's a layout bug — a title that's wider than the source intended is the most common cause.
