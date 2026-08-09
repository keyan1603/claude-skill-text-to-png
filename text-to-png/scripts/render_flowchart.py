#!/usr/bin/env python3
"""Render a simple box-and-arrow flowchart (described as JSON) into a PNG.

This is for turning an ASCII diagram into a *real* diagram — clean rounded
boxes, straight arrows, proper fan-out/fan-in branching — as opposed to
render_text_png.py, which just rasterizes text/ASCII art as-is.

Spec format (pass via --spec <file.json> or --spec-json '<inline json>'):

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

Each row is drawn top to bottom. A row's "label" annotates the arrow(s)
leading INTO that row from the previous one. Rows can have one node
(straight flow) or several (an even fan-out from a single-node row, or a
fan-in into a single-node row).

Node types:
  - "plain": borderless bold centered text. "lines": list of strings (one per line).
  - "box": rounded rectangle. "title" (bold header) plus EITHER "subtitle"
    (a single centered regular-weight line) OR "bullets" (a left-aligned,
    word-wrapped bullet list) — not both.
"""

import argparse
import json
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_REG = None
FONT_BOLD = None
FONT_ITALIC = None

FONT_CANDIDATES = {
    "regular": [
        r"C:\Windows\Fonts\segoeui.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "bold": [
        r"C:\Windows\Fonts\segoeuib.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "italic": [
        r"C:\Windows\Fonts\segoeuii.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ],
}


def find_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[kind]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    print(f"Warning: no {kind} font found; falling back to PIL default bitmap font.", file=sys.stderr)
    return ImageFont.load_default()


BG = "#ffffff"
BOX_FILL = "#f4f7fc"
BOX_EDGE = "#33507a"
TEXT_COLOR = "#1a1a1a"
SUB_COLOR = "#33455e"
ANNOT_COLOR = "#7a7a7a"
LINE_COLOR = "#33507a"

PAD_X, PAD_Y = 20, 16
ROW_GAP = 60          # vertical space between rows, for connector + label
NODE_GAP = 40         # horizontal space between sibling nodes in a fan row
MARGIN = 40
LABEL_CLEARANCE = 22  # extra vertical room reserved when a row has a label


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


class Node:
    def __init__(self, spec):
        self.spec = spec
        self.type = spec["type"]
        self.width = 0
        self.height = 0
        self.draw_lines = []  # list of (text, font_kind, align) for boxes; unused for plain

    def measure(self, draw, title_font, sub_font, bullet_font):
        if self.type == "plain":
            lines = self.spec["lines"]
            widths = [text_w(draw, line, title_font) for line in lines]
            self.width = max(widths) + PAD_X
            self.height = len(lines) * 28
            self._plain_lines = lines
            return self.width, self.height

        title = self.spec["title"]
        subtitle = self.spec.get("subtitle")
        bullets = self.spec.get("bullets")

        if bullets:
            max_content_w = 420
            title_w = text_w(draw, title, title_font)
            wrapped = []
            for b in bullets:
                wrapped.extend(wrap_text(draw, "\u2022 " + b, bullet_font, max_content_w))
            bullet_w = max((text_w(draw, line, bullet_font) for line in wrapped), default=0)
            self.width = max(title_w, bullet_w, 260) + PAD_X * 2
            self.height = PAD_Y * 2 + 26 + 8 + 22 * len(wrapped)
            self._bullets = wrapped
        else:
            title_w = text_w(draw, title, title_font)
            sub_w = text_w(draw, subtitle, sub_font) if subtitle else 0
            self.width = max(title_w, sub_w, 160) + PAD_X * 2 + 20
            self.height = PAD_Y * 2 + 26 + (24 if subtitle else 0)
            self._bullets = None

        return self.width, self.height


def draw_node(draw, node, cx, top, title_font, sub_font, bullet_font, box_title_font):
    if node.type == "plain":
        y = top
        for line in node._plain_lines:
            w = text_w(draw, line, box_title_font)
            draw.text((cx - w / 2, y), line, font=box_title_font, fill=TEXT_COLOR)
            y += 28
        return

    x0, y0 = cx - node.width / 2, top
    x1, y1 = cx + node.width / 2, top + node.height
    draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=BOX_FILL, outline=BOX_EDGE, width=2)

    title = node.spec["title"]
    if node._bullets is not None:
        tw = text_w(draw, title, title_font)
        draw.text((x0 + PAD_X, y0 + PAD_Y), title, font=title_font, fill=TEXT_COLOR)
        ty = y0 + PAD_Y + 26 + 8
        for line in node._bullets:
            draw.text((x0 + PAD_X, ty), line, font=bullet_font, fill=SUB_COLOR)
            ty += 22
    else:
        subtitle = node.spec.get("subtitle")
        if subtitle:
            tw = text_w(draw, title, title_font)
            draw.text((cx - tw / 2, y0 + PAD_Y), title, font=title_font, fill=TEXT_COLOR)
            sw = text_w(draw, subtitle, sub_font)
            draw.text((cx - sw / 2, y0 + PAD_Y + 26), subtitle, font=sub_font, fill=SUB_COLOR)
        else:
            tw = text_w(draw, title, title_font)
            draw.text((cx - tw / 2, y0 + (node.height - 20) / 2), title, font=title_font, fill=TEXT_COLOR)


def arrow_down(draw, x, y_top, y_bottom):
    draw.line([(x, y_top), (x, y_bottom - 9)], fill=LINE_COLOR, width=3)
    draw.polygon([(x - 7, y_bottom - 9), (x + 7, y_bottom - 9), (x, y_bottom)], fill=LINE_COLOR)


def stem_with_label(draw, x, y_top, y_bottom, label, annot_font, side_label=False):
    """Draw a vertical line from y_top to y_bottom, leaving a gap for the
    label (if any) so text never sits on top of the line."""
    if not label:
        draw.line([(x, y_top), (x, y_bottom)], fill=LINE_COLOR, width=3)
        return
    label_h = 20
    label_y = y_top + (y_bottom - y_top) / 2 - label_h / 2
    if side_label:
        draw.line([(x, y_top), (x, y_bottom)], fill=LINE_COLOR, width=3)
        draw.text((x + 16, label_y), label, font=annot_font, fill=ANNOT_COLOR)
    else:
        tw = text_w(draw, label, annot_font)
        draw.line([(x, y_top), (x, label_y - 2)], fill=LINE_COLOR, width=3)
        draw.line([(x, label_y + label_h + 2), (x, y_bottom)], fill=LINE_COLOR, width=3)
        draw.text((x - tw / 2, label_y), label, font=annot_font, fill=ANNOT_COLOR)


def draw_connector(draw, prev_xs, prev_bottom, curr_xs, curr_top, label, annot_font):
    """prev_xs / curr_xs: x-centers of nodes in the previous/current row."""
    if len(prev_xs) == 1 and len(curr_xs) == 1:
        x = prev_xs[0]
        stem_with_label(draw, x, prev_bottom, curr_top - 9, label, annot_font, side_label=True)
        draw.polygon([(x - 7, curr_top - 9), (x + 7, curr_top - 9), (x, curr_top)], fill=LINE_COLOR)
        return

    collapse_x = sum(prev_xs) / len(prev_xs)

    if len(prev_xs) > 1:
        bar_y = prev_bottom + 20
        for x in prev_xs:
            draw.line([(x, prev_bottom), (x, bar_y)], fill=LINE_COLOR, width=3)
        draw.line([(min(prev_xs), bar_y), (max(prev_xs), bar_y)], fill=LINE_COLOR, width=3)
        stem_start = bar_y
    else:
        stem_start = prev_bottom

    stem_end = (curr_top - 20) if len(curr_xs) > 1 else curr_top
    stem_with_label(draw, collapse_x, stem_start, stem_end, label, annot_font, side_label=False)

    if len(curr_xs) > 1:
        bar_y = stem_end
        draw.line([(min(curr_xs), bar_y), (max(curr_xs), bar_y)], fill=LINE_COLOR, width=3)
        for x in curr_xs:
            arrow_down(draw, x, bar_y, curr_top)


def render(spec, output_path):
    dummy = Image.new("RGB", (10, 10))
    ddraw = ImageDraw.Draw(dummy)

    title_font = find_font("bold", 18)
    sub_font = find_font("regular", 15)
    bullet_font = find_font("regular", 15)
    box_title_font = find_font("bold", 20)
    annot_font = find_font("italic", 15)

    rows = []
    for row_spec in spec["rows"]:
        nodes = [Node(n) for n in row_spec["nodes"]]
        for n in nodes:
            n.measure(ddraw, title_font, sub_font, bullet_font)
        row_width = sum(n.width for n in nodes) + NODE_GAP * (len(nodes) - 1)
        row_height = max(n.height for n in nodes)
        rows.append({"nodes": nodes, "label": row_spec.get("label"), "width": row_width, "height": row_height})

    canvas_w = max(r["width"] for r in rows) + MARGIN * 2
    cx = canvas_w / 2

    y = MARGIN
    row_layouts = []
    prev_xs = None
    for i, row in enumerate(rows):
        if i > 0:
            gap = ROW_GAP + (LABEL_CLEARANCE if row["label"] else 0)
            y += gap
        top = y
        n_nodes = len(row["nodes"])
        total_w = row["width"]
        start_x = cx - total_w / 2
        xs = []
        x = start_x
        for n in row["nodes"]:
            node_cx = x + n.width / 2
            xs.append(node_cx)
            x += n.width + NODE_GAP
        row_layouts.append({"top": top, "bottom": top + row["height"], "xs": xs, "nodes": row["nodes"], "label": row["label"]})
        y = top + row["height"]
        prev_xs = xs

    canvas_h = y + MARGIN
    img = Image.new("RGB", (int(canvas_w), int(canvas_h)), BG)
    draw = ImageDraw.Draw(img)

    for i, rl in enumerate(row_layouts):
        for n, x in zip(rl["nodes"], rl["xs"]):
            draw_node(draw, n, x, rl["top"], title_font, sub_font, bullet_font, box_title_font)
        if i > 0:
            prev = row_layouts[i - 1]
            draw_connector(draw, prev["xs"], prev["bottom"], rl["xs"], rl["top"], rl["label"], annot_font)

    img.save(output_path)
    print(f"Saved {int(canvas_w)}x{int(canvas_h)} to {output_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec", help="Path to a JSON spec file")
    src.add_argument("--spec-json", help="Inline JSON spec string")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()

    if args.spec:
        with open(args.spec, encoding="utf-8") as f:
            spec = json.load(f)
    else:
        spec = json.loads(args.spec_json)

    render(spec, args.output)


if __name__ == "__main__":
    main()
