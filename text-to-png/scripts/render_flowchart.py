#!/usr/bin/env python3
"""Render a simple box-and-arrow flowchart (described as JSON) into a PNG.

This is for turning an ASCII diagram into a *real* diagram — clean rounded
boxes, straight arrows, proper branching — as opposed to render_text_png.py,
which just rasterizes text/ASCII art as-is.

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

Each entry in "rows" is either:
  - a normal row: {"nodes": [...], "label": "optional, annotates the arrow into this row"}.
    One node = straight flow. Several nodes = fan-out (if the previous row had
    one node) or fan-in (if the next row has one node) — for branches that
    reconverge onto a shared next step.
  - a branch point (does NOT reconverge — each branch is independent from
    here on, e.g. a guardrail that either terminates the flow or continues
    down a completely different path):
      {"type": "branch", "branches": [
          {"label": "blocked", "rows": [...]},
          {"label": "safe", "rows": [...]}
      ]}
    A branch must be the LAST entry in its "rows" list (nothing reconverges
    after it). Each branch's own "rows" list follows the exact same rules
    recursively, so a branch can itself end in another branch.

Node types:
  - "plain": borderless bold centered text. "lines": list of strings (one per line).
  - "box": rounded rectangle. "title" (bold header) plus AT MOST ONE of:
    "subtitle" (a single centered regular-weight line), "bullets" (a
    left-aligned, word-wrapped bullet list), or "paragraph" (a left-aligned,
    word-wrapped block of text with no bullet marker, for a plain descriptive
    blurb under the title).
"""

import argparse
import json
import sys

from PIL import Image, ImageDraw, ImageFont

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
ROW_GAP = 60           # vertical space between rows, for connector + label
NODE_GAP = 40          # horizontal space between sibling nodes in a fan row
HCHAIN_GAP = 70         # horizontal space between nodes in a left-to-right chain (room for the arrow)
COLUMN_GAP = 60         # horizontal space between sibling branch columns
MARGIN = 40
LABEL_CLEARANCE = 22    # extra vertical room reserved when a row has a label
BRANCH_STEM = 26        # vertical drop from parent to the branch bar
BRANCH_ARROW_DROP = 30  # vertical drop from the branch bar into each column
SIDE_GAP = 50            # horizontal space from the main line to a side-exit node
SIDE_BRANCH_DROP = 22    # vertical offset from a row's bottom to its side-exit tee point


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


class Fonts:
    def __init__(self):
        self.title = find_font("bold", 18)
        self.sub = find_font("regular", 15)
        self.body = find_font("regular", 15)
        self.plain = find_font("bold", 20)
        self.annot = find_font("italic", 15)


class Node:
    def __init__(self, spec):
        self.spec = spec
        self.type = spec["type"]

    def measure(self, draw, fonts):
        if self.type == "plain":
            self._plain_lines = None
            self._plain_title = None
            self._plain_detail = None
            if "title" in self.spec:
                title = self.spec["title"]
                title_lines = title if isinstance(title, list) else [title]
                detail = self.spec.get("detail", [])
                title_w = max((text_w(draw, t, fonts.plain) for t in title_lines), default=0)
                detail_w = max((text_w(draw, l, fonts.sub) for l in detail), default=0)
                self.width = max(title_w, detail_w) + PAD_X
                self.height = 28 * len(title_lines) + (4 + 20 * len(detail) if detail else 0)
                self._plain_title = title_lines
                self._plain_detail = detail
            else:
                lines = self.spec["lines"]
                widths = [text_w(draw, line, fonts.plain) for line in lines]
                self.width = max(widths) + PAD_X
                self.height = len(lines) * 28
                self._plain_lines = lines
            return self.width, self.height

        title = self.spec["title"]
        title_lines = title if isinstance(title, list) else [title]
        title_h = 26 * len(title_lines)
        subtitle = self.spec.get("subtitle")
        bullets = self.spec.get("bullets")
        paragraph = self.spec.get("paragraph")

        self._title_lines = title_lines
        self._bullets = None
        self._paragraph_lines = None

        if bullets:
            max_content_w = 420
            title_w = max(text_w(draw, t, fonts.title) for t in title_lines)
            wrapped = []
            for b in bullets:
                wrapped.extend(wrap_text(draw, "\u2022 " + b, fonts.body, max_content_w))
            body_w = max((text_w(draw, line, fonts.body) for line in wrapped), default=0)
            self.width = max(title_w, body_w, 260) + PAD_X * 2
            self.height = PAD_Y * 2 + title_h + 8 + 22 * len(wrapped)
            self._bullets = wrapped
        elif paragraph:
            max_content_w = 340
            title_w = max(text_w(draw, t, fonts.title) for t in title_lines)
            wrapped = wrap_text(draw, paragraph, fonts.body, max_content_w)
            body_w = max((text_w(draw, line, fonts.body) for line in wrapped), default=0)
            self.width = max(title_w, body_w, 260) + PAD_X * 2
            self.height = PAD_Y * 2 + title_h + 8 + 20 * len(wrapped)
            self._paragraph_lines = wrapped
        else:
            title_w = max(text_w(draw, t, fonts.title) for t in title_lines)
            sub_w = text_w(draw, subtitle, fonts.sub) if subtitle else 0
            self.width = max(title_w, sub_w, 160) + PAD_X * 2 + 20
            self.height = PAD_Y * 2 + title_h + (24 if subtitle else 0)

        return self.width, self.height


def draw_node(draw, node, cx, top, fonts):
    if node.type == "plain":
        if node._plain_title is not None:
            ty = top
            for t in node._plain_title:
                w = text_w(draw, t, fonts.plain)
                draw.text((cx - w / 2, ty), t, font=fonts.plain, fill=TEXT_COLOR)
                ty += 28
            ty += 4 if node._plain_detail else 0
            for line in node._plain_detail:
                lw = text_w(draw, line, fonts.sub)
                draw.text((cx - lw / 2, ty), line, font=fonts.sub, fill=SUB_COLOR)
                ty += 20
            return
        y = top
        for line in node._plain_lines:
            w = text_w(draw, line, fonts.plain)
            draw.text((cx - w / 2, y), line, font=fonts.plain, fill=TEXT_COLOR)
            y += 28
        return

    x0, y0 = cx - node.width / 2, top
    x1, y1 = cx + node.width / 2, top + node.height
    draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=BOX_FILL, outline=BOX_EDGE, width=2)

    title_lines = node._title_lines
    title_h = 26 * len(title_lines)
    if node._bullets is not None:
        ty = y0 + PAD_Y
        for t in title_lines:
            draw.text((x0 + PAD_X, ty), t, font=fonts.title, fill=TEXT_COLOR)
            ty += 26
        ty += 8
        for line in node._bullets:
            draw.text((x0 + PAD_X, ty), line, font=fonts.body, fill=SUB_COLOR)
            ty += 22
    elif node._paragraph_lines is not None:
        ty = y0 + PAD_Y
        for t in title_lines:
            draw.text((x0 + PAD_X, ty), t, font=fonts.title, fill=TEXT_COLOR)
            ty += 26
        ty += 8
        for line in node._paragraph_lines:
            draw.text((x0 + PAD_X, ty), line, font=fonts.body, fill=SUB_COLOR)
            ty += 20
    else:
        subtitle = node.spec.get("subtitle")
        if subtitle:
            ty = y0 + PAD_Y
            for t in title_lines:
                tw = text_w(draw, t, fonts.title)
                draw.text((cx - tw / 2, ty), t, font=fonts.title, fill=TEXT_COLOR)
                ty += 26
            sw = text_w(draw, subtitle, fonts.sub)
            draw.text((cx - sw / 2, ty), subtitle, font=fonts.sub, fill=SUB_COLOR)
        else:
            ty = y0 + (node.height - title_h) / 2
            for t in title_lines:
                tw = text_w(draw, t, fonts.title)
                draw.text((cx - tw / 2, ty), t, font=fonts.title, fill=TEXT_COLOR)
                ty += 26


def arrow_down(draw, x, y_top, y_bottom):
    draw.line([(x, y_top), (x, y_bottom - 9)], fill=LINE_COLOR, width=3)
    draw.polygon([(x - 7, y_bottom - 9), (x + 7, y_bottom - 9), (x, y_bottom)], fill=LINE_COLOR)


def arrow_horizontal(draw, x_from, x_to, y):
    """Horizontal arrow from x_from to x_to, arrowhead at x_to. Works in
    either direction (x_to can be left or right of x_from)."""
    if x_to >= x_from:
        draw.line([(x_from, y), (x_to - 9, y)], fill=LINE_COLOR, width=3)
        draw.polygon([(x_to - 9, y - 7), (x_to - 9, y + 7), (x_to, y)], fill=LINE_COLOR)
    else:
        draw.line([(x_from, y), (x_to + 9, y)], fill=LINE_COLOR, width=3)
        draw.polygon([(x_to + 9, y - 7), (x_to + 9, y + 7), (x_to, y)], fill=LINE_COLOR)


def stem_with_label(draw, x, y_top, y_bottom, label, fonts, side_label=False):
    """Vertical line from y_top to y_bottom, leaving a gap for the label (if
    any) so text never sits on top of the line."""
    if not label:
        draw.line([(x, y_top), (x, y_bottom)], fill=LINE_COLOR, width=3)
        return
    label_h = 20
    label_y = y_top + (y_bottom - y_top) / 2 - label_h / 2
    if side_label:
        draw.line([(x, y_top), (x, y_bottom)], fill=LINE_COLOR, width=3)
        draw.text((x + 16, label_y), label, font=fonts.annot, fill=ANNOT_COLOR)
    else:
        tw = text_w(draw, label, fonts.annot)
        draw.line([(x, y_top), (x, label_y - 2)], fill=LINE_COLOR, width=3)
        draw.line([(x, label_y + label_h + 2), (x, y_bottom)], fill=LINE_COLOR, width=3)
        draw.text((x - tw / 2, label_y), label, font=fonts.annot, fill=ANNOT_COLOR)


def draw_connector(draw, prev_xs, prev_bottom, curr_xs, curr_top, label, fonts):
    """prev_xs / curr_xs: x-centers of nodes in the previous/current row."""
    if len(prev_xs) == 1 and len(curr_xs) == 1:
        x = prev_xs[0]
        stem_with_label(draw, x, prev_bottom, curr_top - 9, label, fonts, side_label=True)
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
    stem_with_label(draw, collapse_x, stem_start, stem_end, label, fonts, side_label=False)

    if len(curr_xs) > 1:
        bar_y = stem_end
        draw.line([(min(curr_xs), bar_y), (max(curr_xs), bar_y)], fill=LINE_COLOR, width=3)
        for x in curr_xs:
            arrow_down(draw, x, bar_y, curr_top)


class Block:
    """A vertical sequence of rows, optionally ending in a non-reconverging
    branch into sibling sub-blocks placed side by side."""

    def __init__(self, rows_spec, draw, fonts):
        self.linear = []
        self.branch = None

        for item in rows_spec:
            if item.get("type") == "branch":
                self.branch = item
                break
            is_hchain = item.get("type") == "hchain"
            nodes = [Node(n) for n in item["nodes"]]
            for n in nodes:
                n.measure(draw, fonts)
            gap = HCHAIN_GAP if is_hchain else NODE_GAP
            width = sum(n.width for n in nodes) + gap * (len(nodes) - 1)
            height = max(n.height for n in nodes)

            side_exit = None
            se_spec = item.get("side_exit")
            if se_spec:
                se_node = Node(se_spec["node"])
                se_node.measure(draw, fonts)
                side_exit = {"label": se_spec.get("label"), "node": se_node}

            self.linear.append({
                "nodes": nodes, "label": item.get("label"), "width": width, "height": height,
                "hchain": is_hchain, "direction": item.get("direction", "right"),
                "side_exit": side_exit,
            })

        self.branch_children = []
        if self.branch:
            for b in self.branch["branches"]:
                self.branch_children.append({"label": b.get("label"), "block": Block(b["rows"], draw, fonts)})

        linear_width = max((r["width"] for r in self.linear), default=0)
        linear_height = 0
        for i, r in enumerate(self.linear):
            if i > 0:
                linear_height += ROW_GAP + (LABEL_CLEARANCE if r["label"] else 0)
            linear_height += r["height"]

        self.right_extra = 0
        for r in self.linear:
            if r["side_exit"]:
                self.right_extra = max(self.right_extra, SIDE_GAP + r["side_exit"]["node"].width)

        if self.branch_children:
            branch_widths = [c["block"].width + c["block"].right_extra for c in self.branch_children]
            branch_section_width = sum(branch_widths) + COLUMN_GAP * (len(self.branch_children) - 1)
            branch_section_height = max(c["block"].height for c in self.branch_children)
            fanout_height = BRANCH_STEM + BRANCH_ARROW_DROP
            self.width = max(linear_width, branch_section_width)
            self.height = linear_height + (fanout_height if self.linear else 0) + branch_section_height
            self.right_extra = max(self.right_extra, self.branch_children[-1]["block"].right_extra)
        else:
            self.width = linear_width
            self.height = linear_height

    def draw(self, draw, cx, top, fonts):
        y = top
        last_xs = None
        for i, r in enumerate(self.linear):
            total_w = r["width"]
            start_x = cx - total_w / 2
            gap = HCHAIN_GAP if r["hchain"] else NODE_GAP
            reversed_dir = r["hchain"] and r["direction"] == "left"
            # display_nodes is the spatial left-to-right order; for a
            # right-to-left hchain that's the reverse of flow order.
            display_nodes = list(reversed(r["nodes"])) if reversed_dir else r["nodes"]

            positions = []
            x = start_x
            for n in display_nodes:
                node_cx = x + n.width / 2
                positions.append(node_cx)
                x += n.width + gap

            if r["hchain"]:
                # entry = flow-first node's position, exit = flow-last node's position
                entry_xs = [positions[-1] if reversed_dir else positions[0]]
                exit_xs = [positions[0] if reversed_dir else positions[-1]]
            else:
                entry_xs = positions
                exit_xs = positions

            if i > 0:
                y += ROW_GAP + (LABEL_CLEARANCE if r["label"] else 0)
                draw_connector(draw, last_xs, last_bottom, entry_xs, y, r["label"], fonts)
            for n, x in zip(display_nodes, positions):
                draw_node(draw, n, x, y, fonts)
            if r["hchain"]:
                arrow_y = y + 14
                for j in range(len(display_nodes) - 1):
                    left_n, right_n = display_nodes[j], display_nodes[j + 1]
                    edge_left = positions[j] + left_n.width / 2
                    edge_right = positions[j + 1] - right_n.width / 2
                    if reversed_dir:
                        arrow_horizontal(draw, edge_right, edge_left, arrow_y)
                    else:
                        arrow_horizontal(draw, edge_left, edge_right, arrow_y)
            if r["side_exit"]:
                se = r["side_exit"]
                branch_x = sum(exit_xs) / len(exit_xs)
                branch_y = y + r["height"] + SIDE_BRANCH_DROP
                draw.line([(branch_x, y + r["height"]), (branch_x, branch_y)], fill=LINE_COLOR, width=3)
                se_node = se["node"]
                se_left = branch_x + SIDE_GAP
                se_cx = se_left + se_node.width / 2
                se_top = branch_y - se_node.height / 2
                arrow_horizontal(draw, branch_x, se_left, branch_y)
                if se["label"]:
                    draw.text((branch_x + 10, branch_y - 24), se["label"], font=fonts.annot, fill=ANNOT_COLOR)
                draw_node(draw, se_node, se_cx, se_top, fonts)

            last_xs = exit_xs
            last_bottom = y + r["height"]
            y = last_bottom

        if self.branch_children:
            parent_x = (sum(last_xs) / len(last_xs)) if last_xs else cx
            parent_bottom = last_bottom if self.linear else top

            bar_y = parent_bottom + BRANCH_STEM
            draw.line([(parent_x, parent_bottom), (parent_x, bar_y)], fill=LINE_COLOR, width=3)

            n = len(self.branch_children)
            eff_widths = [c["block"].width + c["block"].right_extra for c in self.branch_children]
            total_w = sum(eff_widths) + COLUMN_GAP * (n - 1)
            start_x = cx - total_w / 2
            col_positions = []
            x = start_x
            for c, eff_w in zip(self.branch_children, eff_widths):
                col_cx = x + c["block"].width / 2
                col_positions.append(col_cx)
                x += eff_w + COLUMN_GAP

            draw.line([(min(col_positions), bar_y), (max(col_positions), bar_y)], fill=LINE_COLOR, width=3)

            content_top = bar_y + BRANCH_ARROW_DROP
            for c, col_cx in zip(self.branch_children, col_positions):
                arrow_down(draw, col_cx, bar_y, content_top)
                if c["label"]:
                    draw.text((col_cx + 10, bar_y + 4), c["label"], font=fonts.annot, fill=ANNOT_COLOR)
                c["block"].draw(draw, col_cx, content_top, fonts)


def render(spec, output_path):
    dummy = Image.new("RGB", (10, 10))
    ddraw = ImageDraw.Draw(dummy)
    fonts = Fonts()

    root = Block(spec["rows"], ddraw, fonts)
    cx = MARGIN + root.width / 2
    canvas_w = root.width + MARGIN * 2 + root.right_extra
    canvas_h = root.height + MARGIN * 2

    img = Image.new("RGB", (int(canvas_w), int(canvas_h)), BG)
    draw = ImageDraw.Draw(img)
    root.draw(draw, cx, MARGIN, fonts)

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
