"""Render arbitrary compact Markdown notes into the bundled Notability template.

Run this script with the virtual environment prepared by bootstrap.ps1.  The
Markdown is an authored, concise transcription, not a prompt for OCR or solving.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys

SKILL_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = SKILL_ROOT / "vendor" / "MarkdownToHandwrite"
if (VENDOR_ROOT / "src").is_dir():
    sys.path.insert(0, str(VENDOR_ROOT / "src"))

from PIL import Image, ImageChops, ImageDraw, ImageOps
from markdown_to_handwrite.config import load_config, mm_to_px, pt_to_px
from markdown_to_handwrite.markdown_parser import (
    CodeBlock, FormulaBlock, HeadingBlock, ImageBlock, InlinePart, ListBlock,
    PageBreakBlock, ParagraphBlock, TableBlock, parse_markdown,
)
from markdown_to_handwrite.math_renderer import (
    AccentNode, FormulaRenderer, LatexMathParser, MathBox, _formula_lines,
    _has_equation_tag, _parse_display_rows, _strip_math_delimiters,
)
from markdown_to_handwrite.renderer import ReportRenderer
from markdown_to_handwrite.typography import westernize_punctuation
from font_mixing import MixedFontEngine


def enable_unboxed_commands():
    if getattr(LatexMathParser, "_notability_unboxed", False):
        return
    original = LatexMathParser._parse_command

    def command(parser):
        for name in (r"\boxed", r"\fbox"):
            end = parser.index + len(name)
            if parser.source.startswith(name, parser.index) and (
                end == len(parser.source) or not parser.source[end].isalpha()
            ):
                parser.index = end
                return AccentNode(parser._parse_argument(), "notability-unboxed")
        return original(parser)

    LatexMathParser._parse_command = command
    LatexMathParser._notability_unboxed = True


class LeftFormulaRenderer(FormulaRenderer):
    def _stack(self, boxes, size):
        if not boxes:
            return MathBox(self.blank_display(size), round(size * 0.75))
        gap = max(4, round(size * 0.4))
        width = max(box.width for box in boxes)
        height = sum(box.height for box in boxes) + gap * (len(boxes) - 1)
        result = Image.new("RGBA", (width, height))
        y = 0
        for box in boxes:
            result.alpha_composite(box.image, (0, y))
            y += box.height + gap
        baseline = boxes[0].baseline if len(boxes) == 1 else height // 2 + round(size * 0.25)
        return MathBox(result, min(height, baseline))

    def render(self, latex, size_px, max_width, seed_extra=""):
        latex = westernize_punctuation(latex)
        if _has_equation_tag(latex):
            return self._layout_display_rows(
                _parse_display_rows(_strip_math_delimiters(latex)), size_px, max_width, seed_extra
            ).image
        boxes = [self._layout_with_weight_group(
            LatexMathParser(line).parse(), size_px, f"{seed_extra}:display:{i}", display_style=True
        ) for i, line in enumerate(_formula_lines(latex)) if line.strip()]
        return self._fit_display_box(self._stack(boxes, size_px), max_width).image

    def _layout_display_rows(self, rows, size_px, max_width, seed_extra):
        boxes = []
        for index, row in enumerate(rows):
            seed = f"{seed_extra}:display:{index}"
            if isinstance(row.body, list):
                box = self._layout_display_rows(row.body, size_px, max_width, seed)
            else:
                box = self._fit_display_box(self._layout_with_weight_group(
                    row.body, size_px, seed, display_style=True
                ), max_width)
            if row.tag is not None:
                tag = self._fit_display_box(self._layout_with_weight_group(
                    row.tag, size_px, seed, display_style=False
                ), max_width)
                box = self._place_equation_tag(box, tag, size_px, max_width)
            boxes.append(box)
        return self._stack(boxes, size_px)

    @staticmethod
    def _place_equation_tag(body, tag, size_px, max_width):
        gap = max(4, round(size_px * 0.8))
        tag_x = max_width - tag.width
        if body.width + gap <= tag_x:
            baseline = max(body.baseline, tag.baseline)
            body_y, tag_y = baseline - body.baseline, baseline - tag.baseline
        else:
            body_y, tag_y, baseline = 0, body.height + max(4, round(size_px * 0.4)), body.baseline
        result = Image.new("RGBA", (max_width, max(body_y + body.height, tag_y + tag.height)))
        result.alpha_composite(body.image, (0, body_y))
        result.alpha_composite(tag.image, (tag_x, tag_y))
        return MathBox(result, baseline)

    def _accent_box(self, node, size_px, seed_extra, display_style=False):
        if node.kind == "notability-unboxed":
            return self._layout(node.body, size_px, seed_extra, display_style)
        return super()._accent_box(node, size_px, seed_extra, display_style)


class NotesRenderer(ReportRenderer):
    """Cache actual block rasters for an exact measure/plan/draw workflow."""

    def __init__(self, config, base_dir, columns, font_mode="mixed", new_font_path=None):
        enable_unboxed_commands()
        self.measuring = True
        self.active_token = "init"
        self.rich_cache = {}
        self.formula_cache = {}
        self.image_cache = {}
        self.table_width_override = None
        self.warnings = []
        super().__init__(config, base_dir)
        if font_mode == "mixed":
            self.engine = MixedFontEngine(config.handwriting, self.engine, self.dpi, new_font_path)
        self.formula_renderer = LeftFormulaRenderer(self.engine, seed=config.handwriting.seed)
        self.paper_left = self.margin_left
        self.paper_bottom = self.bottom_limit
        self.capacity = self.paper_bottom - self.margin_top
        self.column_count = columns
        self.gutter = mm_to_px(5.08, self.dpi) if columns == 2 else 0
        self.content_w = (self.content_w - self.gutter * (columns - 1)) // columns
        self.bottom_limit = 10**12

    def _make_background(self):
        if self.measuring:
            return Image.new("RGBA", (1, 1))
        return super()._make_background()

    def _new_page(self):
        if getattr(self, "drawing_locked", False):
            raise RuntimeError("A measured block overflowed its column; no content was clipped.")
        super()._new_page()

    def _ensure_space(self, height):
        if not self.measuring and self.y + height > self.paper_bottom + 1:
            raise RuntimeError("A block exceeds the current column; split this block in the source.")

    def _report_formula_error(self, latex, error):
        raise ValueError(f"Cannot render LaTeX: {latex}\n{error}") from error

    def _layout_rich_parts(self, parts, size, max_width, normal_line_h, seed_extra, first_line_width=None):
        stable_seed = f"{self.active_token}:{seed_extra.split(':', 1)[0]}"
        # Table seed suffixes distinguish cells with equal size and width.
        if "cell:" in seed_extra:
            stable_seed += seed_extra[seed_extra.index("cell:"):]
        key = (repr(parts), size, max_width, normal_line_h, first_line_width, stable_seed)
        if key not in self.rich_cache:
            self.rich_cache[key] = super()._layout_rich_parts(
                parts, size, max_width, normal_line_h, stable_seed, first_line_width
            )
        return self.rich_cache[key]

    def _paste_rich_line(self, *args, **kwargs):
        if not self.measuring:
            return super()._paste_rich_line(*args, **kwargs)

    def _paste_text(self, *args, **kwargs):
        if not self.measuring:
            return super()._paste_text(*args, **kwargs)

    def _formula_indent(self):
        return 2 * pt_to_px(self.config.handwriting.body_font_pt, self.dpi)

    def _render_formula_image(self, text, seed_extra):
        key = (self.active_token, text, self.content_w, self.config.handwriting.math_font_pt)
        if key not in self.formula_cache:
            self.formula_cache[key] = self.formula_renderer.render(
                text, pt_to_px(self.config.handwriting.math_font_pt, self.dpi),
                max(1, self.content_w - self._formula_indent() - mm_to_px(1, self.dpi)),
                seed_extra=f"{self.active_token}:formula:{hashlib.sha256(text.encode()).hexdigest()[:16]}",
            )
        return self.formula_cache[key]

    def _draw_formula(self, text, image=None):
        if not text:
            return
        image = image if image is not None else self._render_formula_image(text, "")
        gap = mm_to_px(self.config.layout.formula_gap_mm, self.dpi)
        self._ensure_space(image.height + 2 * gap)
        self.y += gap
        if not self.measuring:
            self.page.alpha_composite(image, (self.margin_left + self._formula_indent(), self.y))
        self.y += image.height + gap

    def _load_figure(self, block):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", block.src):
            raise ValueError("Images must be local files relative to the Markdown, not URLs.")
        path = Path(block.src)
        if not path.is_absolute():
            path = self.base_dir / path
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Missing diagram: {path}; render it first, do not leave a placeholder.")
        key = (str(path), self.content_w)
        if key not in self.image_cache:
            with Image.open(path) as opened:
                source = opened.convert("RGBA")
            gray = ImageOps.grayscale(source)
            opacity = ImageChops.multiply(ImageOps.invert(gray), source.getchannel("A"))
            image = Image.new("RGBA", source.size, (0, 0, 0, 0))
            image.putalpha(opacity)
            image.thumbnail((self.content_w, max(1, round(self.capacity * 0.9))), Image.Resampling.LANCZOS)
            # Enlarge small diagrams only to the chosen column, preserving aspect ratio.
            if image.width < self.content_w:
                ratio = min(self.content_w / image.width, self.capacity * 0.9 / image.height)
                if ratio > 1:
                    image = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
            self.image_cache[key] = image
        return self.image_cache[key]

    def _draw_image_placeholder(self, block):
        image = self._load_figure(block)
        gap = mm_to_px(1.5, self.dpi)
        self._ensure_space(image.height + gap)
        if not self.measuring:
            self.page.alpha_composite(image, (self.margin_left, self.y))
        self.y += image.height + gap

    def _table_widths(self, block, col_count, size):
        if self.table_width_override is not None:
            return self.table_width_override
        return super()._table_widths(block, col_count, size)

    def _draw_table_row(self, widths, layout, pad, header, draw_top=True):
        cells, height = layout
        x = self.margin_left
        for index, width in enumerate(widths):
            y = self.y + pad
            horizontal_pad, available = self._table_content_geometry(width, pad)
            for line in cells[index]:
                self._paste_rich_line(line, x + horizontal_pad, y, available,
                                      align="left" if index == 0 else "center")
                y += line.height
            x += width
        self.y += height

    def _draw_code(self, block):
        # Technical literal text is borderless, just like data tables.
        parts = []
        for index, line in enumerate(block.text.splitlines()):
            if index:
                parts.append(InlinePart("hardbreak"))
            parts.append(InlinePart("text", line))
        self._draw_rich_paragraph(parts, no_indent=True)

    def draw_block(self, block, token, widths=None):
        self.active_token = token
        self.table_width_override = widths
        try:
            self.render([block])
        finally:
            self.table_width_override = None

    def measure(self, block, token, widths=None):
        self.y = self.margin_top + 1
        start = self.y
        self.draw_block(block, token, widths)
        return self.y - start

    def begin_sheet(self):
        self.measuring = False
        self.drawing_locked = False
        self.bottom_limit = self.paper_bottom
        if getattr(self, "page", None) is not None:
            self.page.close()
        self.pages = []
        self._new_page()
        self.drawing_locked = True


@dataclass
class Unit:
    blocks: list
    tokens: list[str]
    height: int
    heading_start: bool = False
    table_widths: list[int] | None = None


def validate_source(source):
    for number, line in enumerate(source.splitlines(), 1):
        # URLs/paths are data, not visible Chinese labels.
        visible = re.sub(r"(!?\[[^\]]*\])\([^)]*\)", r"\1", line)
        stripped = visible.strip()
        labels = re.split(r"(?<!\\)\|", stripped.strip("|")) if stripped.startswith("|") else [visible]
        for label in labels:
            if len(re.findall(r"[\u3400-\u9fff]", label)) > 4:
                raise ValueError(f"Line {number}: each Chinese label/table cell must contain at most four characters; condense the prose.")


def make_units(renderer, blocks, prefix):
    expanded = []
    for index, block in enumerate(blocks):
        token = f"{prefix}:{index}"
        if isinstance(block, PageBreakBlock):
            continue
        if isinstance(block, ListBlock) and len(block.items) > 1:
            expanded.extend((ListBlock(block.ordered, [item], block.start + item_index),
                             f"{token}:item:{item_index}", None)
                            for item_index, item in enumerate(block.items))
        else:
            expanded.append((block, token, None))
    measured = []
    for block, token, widths in expanded:
        height = renderer.measure(block, token)
        if height > renderer.capacity and isinstance(block, TableBlock) and len(block.rows) > 1:
            size = pt_to_px(renderer.config.handwriting.body_font_pt - 1, renderer.dpi)
            count = max(len(block.headers), *(len(row) for row in block.rows))
            widths = renderer._table_widths(block, count, size)
            chunk = []
            chunk_index = 0
            for row in block.rows:
                proposal = TableBlock(block.headers, chunk + [row])
                proposed_height = renderer.measure(proposal, f"{token}:table:{chunk_index}", widths)
                if proposed_height > renderer.capacity and chunk:
                    fragment = TableBlock(block.headers, chunk)
                    fragment_token = f"{token}:table:{chunk_index}"
                    measured.append((fragment, fragment_token, renderer.measure(fragment, fragment_token, widths), widths))
                    chunk_index += 1
                    chunk = [row]
                else:
                    chunk.append(row)
            if chunk:
                fragment = TableBlock(block.headers, chunk)
                fragment_token = f"{token}:table:{chunk_index}"
                measured.append((fragment, fragment_token, renderer.measure(fragment, fragment_token, widths), widths))
        else:
            measured.append((block, token, height, widths))
    units = []
    index = 0
    while index < len(measured):
        block, token, height, widths = measured[index]
        if height > renderer.capacity:
            raise ValueError(f"Block {token} is taller than a column; split its paragraphs or display equations.")
        selected = [(block, token, height)]
        heading = isinstance(block, HeadingBlock)
        # Do not leave a heading alone at the bottom of a column.
        if heading and index + 1 < len(measured):
            following = measured[index + 1]
            if height + following[2] <= renderer.capacity:
                selected.append(following[:3])
                index += 1
                widths = following[3]
        units.append(Unit([item[0] for item in selected], [item[1] for item in selected],
                          sum(item[2] for item in selected), heading, widths))
        index += 1
    return units


def balanced_columns(units, capacity, columns_per_page, force_minimum=False):
    if not units:
        return []
    prefix = [0]
    for unit in units:
        prefix.append(prefix[-1] + unit.height)
    n = len(units)
    minimum = 1
    used = 0
    for unit in units:
        if used and used + unit.height > capacity:
            minimum += 1
            used = 0
        used += unit.height
    column_count = minimum if force_minimum else min(n, math.ceil(minimum / columns_per_page) * columns_per_page)
    target = prefix[-1] / column_count
    infinity = float("inf")
    previous = [infinity] * (n + 1)
    previous[0] = 0.0
    back = []
    for count in range(1, column_count + 1):
        current = [infinity] * (n + 1)
        cuts = [-1] * (n + 1)
        for end in range(count, n + 1):
            for start in range(end - 1, count - 2, -1):
                height = prefix[end] - prefix[start]
                if height > capacity:
                    break
                if previous[start] == infinity:
                    continue
                cost = previous[start] + (height - target)**2
                if start and not units[start].heading_start:
                    cost += capacity**2 * 0.055
                if cost < current[end]:
                    current[end], cuts[end] = cost, start
        previous = current
        back.append(cuts)
    if previous[n] == infinity:
        raise RuntimeError("Unable to partition notes into safe columns.")
    result = []
    end = n
    for count in range(column_count, 0, -1):
        start = back[count - 1][end]
        result.append(units[start:end])
        end = start
    return list(reversed(result))


def source_segments(source, split_heading):
    if split_heading:
        matched = False
        lines = source.splitlines()
        for index, line in enumerate(lines):
            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
            if heading and (line.strip() == split_heading.strip() or heading.group(1) == split_heading.strip()):
                lines.insert(index, "\n<columnbreak>\n")
                matched = True
                break
        if not matched:
            raise ValueError(f"No heading matches --split-heading {split_heading!r}")
        source = "\n".join(lines)
    pieces = re.split(r"(?im)^\s*<(columnbreak|newpage)\s*/?>\s*$", source)
    result = []
    for index in range(0, len(pieces), 2):
        text = pieces[index]
        after = pieces[index + 1].lower() if index + 1 < len(pieces) else None
        if text.strip():
            result.append((text, after))
        elif result and after:
            result[-1] = (result[-1][0], after)
    return result


def make_config(args):
    path = args.config or SKILL_ROOT / "assets" / "config.json"
    config = load_config(path)
    config.background.style = "image"
    config.background.auto_discover = False
    config.background.image = str((SKILL_ROOT / "assets" / "notability-template.png").resolve())
    config.page.dpi = args.dpi
    hw, layout = config.handwriting, config.layout
    hw.body_font_pt = args.font_size
    hw.math_font_pt = args.font_size + 0.3
    hw.h1_font_pt = hw.h2_font_pt = hw.h3_font_pt = args.font_size + 0.3
    hw.line_spacing = 1.10
    hw.ink_color = "#306BCC"
    hw.word_spacing_px = -0.5 * args.dpi / 240
    hw.sdt_supersample = 2
    if args.seed is not None:
        hw.seed = args.seed
    layout.first_line_indent_em = 0
    layout.paragraph_gap_mm = 0.25
    layout.heading_gap_before_mm = 1.0
    layout.heading_gap_after_mm = 0.35
    layout.formula_gap_mm = 0.20
    layout.table_gap_mm = 0.4
    layout.table_cell_padding_mm = 0.25
    layout.number_sections = layout.show_page_numbers = layout.justify_paragraphs = False
    layout.footer_gap_mm = 0
    font = VENDOR_ROOT / "font" / "1_SDT.ttf"
    if font.is_file():
        hw.font_path = str(font.resolve())
        hw.math_font_path = str(font.resolve())
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=720)
    parser.add_argument("--columns", type=int, choices=(1, 2), default=2)
    parser.add_argument("--split-heading")
    parser.add_argument("--font-size", type=float, default=6.6)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--font-mode", choices=("mixed", "old"), default="mixed")
    parser.add_argument("--new-font", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args(argv)
    if not 96 <= args.dpi <= 1200:
        parser.error("--dpi must be between 96 and 1200")
    if not 4 <= args.font_size <= 18:
        parser.error("--font-size must be between 4 and 18 points")
    input_path = args.input.resolve()
    source = input_path.read_text(encoding="utf-8-sig")
    if not source.strip():
        raise ValueError("The input Markdown is empty.")
    validate_source(source)
    segments = source_segments(source, args.split_heading)
    renderer = NotesRenderer(make_config(args), input_path.parent, args.columns, args.font_mode, args.new_font)
    if not renderer.engine.uses_sdt_trajectories:
        raise RuntimeError("SDT trajectories are missing; complete the skill bootstrap first.")
    plan = []
    forced = len(segments) > 1 or any(after for _, after in segments)
    for index, (text, after) in enumerate(segments):
        units = make_units(renderer, parse_markdown(text), f"segment:{index}")
        plan.extend(balanced_columns(units, renderer.capacity, args.columns, force_minimum=forced))
        if after == "newpage" and len(plan) % args.columns:
            plan.extend([[]] * (args.columns - len(plan) % args.columns))
    if not plan:
        raise ValueError("The input contains no renderable content.")
    while plan and not plan[-1]:
        plan.pop()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {"source": input_path.name, "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "dpi": args.dpi, "columns_per_page": args.columns, "ink": "#306BCC", "plot_ink": "#000000",
              "formula_align": "left", "formula_indent_em": 2, "formula_indent_px": renderer._formula_indent(),
              "max_chinese_label": 4, "table_borders": False, "answer_boxes": False,
              "paper_bounds_px": [renderer.paper_left, renderer.margin_top,
                                  renderer.page_w - renderer.margin_right, renderer.paper_bottom],
              "images": []}
    for page_index, offset in enumerate(range(0, len(plan), args.columns), 1):
        renderer.begin_sheet()
        geometry = []
        for column_index, units in enumerate(plan[offset:offset + args.columns]):
            renderer.margin_left = renderer.paper_left + column_index * (renderer.content_w + renderer.gutter)
            renderer.y = renderer.margin_top
            for unit in units:
                for block, token in zip(unit.blocks, unit.tokens):
                    renderer.draw_block(block, token, unit.table_widths)
            geometry.append({"x": renderer.margin_left, "used_height": renderer.y - renderer.margin_top,
                             "available_height": renderer.capacity, "block_count": sum(len(u.blocks) for u in units)})
        filename = f"notes-{page_index:02}.png"
        preview_name = f"notes-{page_index:02}-preview.png"
        rendered = renderer.page.convert("RGB")
        rendered.save(output / filename, optimize=True, dpi=(args.dpi, args.dpi))
        rendered.thumbnail((3092, 2158), Image.Resampling.LANCZOS)
        rendered.save(output / preview_name, optimize=True)
        result["images"].append({"file": filename, "preview": preview_name,
                                  "width": renderer.page_w, "height": renderer.page_h, "columns": geometry})
        print(f"Saved {filename} ({renderer.page_w}x{renderer.page_h})", flush=True)
    result["font_mixing"] = (renderer.engine.diagnostics() if isinstance(renderer.engine, MixedFontEngine)
                             else {"mode": "old"})
    (output / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest: {output / 'manifest.json'}", flush=True)


if __name__ == "__main__":
    main()
