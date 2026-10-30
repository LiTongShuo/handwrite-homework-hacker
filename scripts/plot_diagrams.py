"""Draw standard black scientific diagrams from a restricted JSON specification."""

from __future__ import annotations

import argparse
import ast
import json
import math
import operator
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

INK = (0, 0, 0, 255)
FUNCTIONS = {"sin": np.sin, "cos": np.cos, "tan": np.tan,
             "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs,
             "log": np.log, "log10": np.log10, "sinh": np.sinh,
             "cosh": np.cosh}
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub,
             ast.Mult: operator.mul, ast.Div: operator.truediv,
             ast.Mod: operator.mod, ast.Pow: np.power}


def evaluate_expression(expression: str, x: np.ndarray) -> np.ndarray:
    """Interpret an arithmetic AST; never execute Python code or attribute access."""
    if not isinstance(expression, str) or len(expression) > 2048:
        raise ValueError("Expression must be a string of at most 2048 characters.")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise ValueError("Expression is too complex.")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
            if not math.isfinite(value) or abs(value) > 1e100:
                raise ValueError("Numeric constant is outside the supported range.")
            return value
        if isinstance(node, ast.Name):
            if node.id in ("x", "t"):
                return x
            if node.id == "pi":
                return math.pi
            if node.id == "e":
                return math.e
            raise ValueError(f"Unknown variable: {node.id}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and np.any(np.abs(right) > 32):
                raise ValueError("Power exponent magnitude must not exceed 32.")
            return OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in FUNCTIONS or len(node.args) != 1 or node.keywords:
                raise ValueError("Only the listed single-argument math functions are allowed.")
            return FUNCTIONS[node.func.id](visit(node.args[0]))
        raise ValueError(f"Unsupported expression syntax: {type(node).__name__}")

    with np.errstate(all="ignore"):
        values = np.asarray(visit(tree), dtype=float)
    try:
        return np.broadcast_to(values, x.shape)
    except ValueError as error:
        raise ValueError("Expression must return one number per x value.") from error


def find_font(explicit: str | None = None, italic: bool = False) -> str:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Font does not exist: {path}")
        return str(path)
    candidates = (["C:/Windows/Fonts/timesi.ttf", "C:/Windows/Fonts/cambriai.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf"]
                  if italic else
                  ["C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/cambria.ttc",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"])
    candidates += ["/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                   "/Library/Fonts/Times New Roman.ttf"]
    bundled = Path(__file__).resolve().parents[1] / "assets/fonts"
    candidates.append(str(bundled / ("DejaVuSerif-Italic.ttf" if italic else "DejaVuSerif.ttf")))
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    for family in ("DejaVuSerif.ttf", "LiberationSerif-Regular.ttf", "Times New Roman.ttf"):
        try:
            ImageFont.truetype(family, 16)
            return family
        except OSError:
            pass
    raise RuntimeError("No standard plot font found. Supply --font with a local font file.")


def finite_pair(value, default, field):
    value = default if value is None else value
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{field} requires two numbers.")
    lo, hi = map(float, value)
    if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
        raise ValueError(f"{field} must be finite and increasing.")
    return lo, hi


def ticks(values, lo, hi):
    if values is None:
        return [(float(v), f"{v:g}".replace("-", "−")) for v in np.linspace(lo, hi, 5)]
    result = []
    for value in values:
        number, label = (value, f"{value:g}") if isinstance(value, (int, float)) else (value[0], str(value[1]))
        number = float(number)
        if not math.isfinite(number):
            raise ValueError("Tick positions must be finite.")
        if lo <= number <= hi:
            result.append((number, str(label).replace("-", "−")))
    return result


class Panel:
    def __init__(self, width, height, supersample, font=None):
        self.width, self.height, self.ss = width, height, supersample
        self.image = Image.new("RGBA", (width * self.ss, height * self.ss))
        self.draw = ImageDraw.Draw(self.image)
        self.font_path = find_font(font)
        self.italic_path = find_font(font, italic=True)
        self.fonts = {}
        self.size = max(16, width * 0.027)
        self.pen = max(1, width * 0.00125)
        self.left, self.right = width * 0.12, width * 0.93
        self.top, self.bottom = height * 0.17, height * 0.77

    def point(self, x, y):
        return x * self.ss, y * self.ss

    def line(self, a, b, scale=1):
        self.draw.line([self.point(*a), self.point(*b)], fill=INK,
                       width=max(1, round(self.pen * self.ss * scale)))

    def arrow(self, a, b):
        self.line(a, b)
        ax, ay = self.point(*a)
        bx, by = self.point(*b)
        angle = math.atan2(by - ay, bx - ax)
        length = self.width * self.ss * 0.009
        half = length * 0.3
        cx, cy = bx - length * math.cos(angle), by - length * math.sin(angle)
        nx, ny = -math.sin(angle), math.cos(angle)
        self.draw.polygon([(bx, by), (cx + half * nx, cy + half * ny),
                           (cx - half * nx, cy - half * ny)], fill=INK)

    def label(self, text, x, y, anchor="lt", scale=1, italic=False):
        text = str(text)
        runs, buffer, index = [], "", 0
        while index < len(text):
            char = text[index]
            if char not in "_^":
                buffer += char
                index += 1
                continue
            if buffer:
                runs.append((buffer, 1.0, 0.0))
                buffer = ""
            index += 1
            if index < len(text) and text[index] == "{":
                end = text.find("}", index + 1)
                if end < 0:
                    raise ValueError("Unclosed subscript/superscript label group.")
                chunk = text[index + 1:end]
                index = end + 1
            elif index < len(text):
                chunk = text[index]
                index += 1
            else:
                chunk = char
            runs.append((chunk, 0.68, 0.28 if char == "_" else -0.43))
        if buffer:
            runs.append((buffer, 1.0, 0.0))
        if not runs:
            return
        segments, advance, min_y, max_y = [], 0.0, 0.0, 0.0
        base = self.size * scale * self.ss
        for chunk, ratio, shift in runs:
            pixels = max(8, round(base * ratio))
            font_path = self.italic_path if italic and not chunk.replace("−", "").replace(".", "").isdigit() else self.font_path
            key = font_path, pixels
            if key not in self.fonts:
                self.fonts[key] = ImageFont.truetype(font_path, pixels)
            font = self.fonts[key]
            offset = base * shift
            bbox = self.draw.textbbox((0, offset), chunk, font=font, anchor="ls")
            segments.append((chunk, font, advance, offset))
            advance += self.draw.textlength(chunk, font=font)
            min_y, max_y = min(min_y, bbox[1]), max(max_y, bbox[3])
        image = Image.new("RGBA", (math.ceil(advance) + 4, math.ceil(max_y - min_y) + 4))
        draw = ImageDraw.Draw(image)
        for chunk, font, offset_x, offset_y in segments:
            draw.text((2 + offset_x, 2 - min_y + offset_y), chunk, font=font, anchor="ls", fill=INK)
        px, py = self.point(x, y)
        if anchor[0] == "c":
            px -= image.width / 2
        elif anchor[0] == "r":
            px -= image.width
        if anchor[1] == "c":
            py -= image.height / 2
        elif anchor[1] == "b":
            py -= image.height
        px = min(max(0, round(px)), max(0, self.image.width - image.width))
        py = min(max(0, round(py)), max(0, self.image.height - image.height))
        self.image.alpha_composite(image, (px, py))

    def render(self, spec):
        kind = spec.get("type", "curve")
        if kind not in ("curve", "impulses"):
            raise ValueError(f"Unknown panel type: {kind}")
        self.xlo, self.xhi = finite_pair(spec.get("x_range"), [-math.pi, math.pi], "x_range")
        self.ylo, self.yhi = finite_pair(spec.get("y_range"), [-1.2, 1.2], "y_range")
        if kind == "impulses" and not self.ylo <= 0 <= self.yhi:
            raise ValueError("An impulse panel y_range must include zero.")

        def p(x, y):
            return (self.left + (x - self.xlo) / (self.xhi - self.xlo) * (self.right - self.left),
                    self.bottom - (y - self.ylo) / (self.yhi - self.ylo) * (self.bottom - self.top))

        x_axis_y = min(max(0.0, self.ylo), self.yhi) if spec.get("axes_zero", True) else self.ylo
        y_axis_x = min(max(0.0, self.xlo), self.xhi) if spec.get("axes_zero", True) else self.xlo
        x0, y0 = p(y_axis_x, x_axis_y)
        draw_axis = self.arrow if spec.get("arrows", True) else self.line
        draw_axis((self.left, y0), (self.right + self.width * 0.018, y0))
        draw_axis((x0, self.bottom), (x0, self.top - self.height * 0.018))
        if spec.get("title"):
            self.label(spec["title"], self.left, self.height * 0.02, scale=1.0)
        if spec.get("x_label"):
            self.label(spec["x_label"], self.right + self.width * 0.018, self.height * 0.98,
                       anchor="rb", scale=0.92, italic=True)
        if spec.get("y_label"):
            self.label(spec["y_label"], x0 + self.width * 0.012, self.top - self.height * 0.04,
                       anchor="lb", scale=0.95, italic=True)
        xticks = ticks(spec.get("x_ticks"), self.xlo, self.xhi)
        yticks = ticks(spec.get("y_ticks"), self.ylo, self.yhi)
        for value, label in xticks:
            px, _ = p(value, x_axis_y)
            self.line((px, y0 - 4), (px, y0 + 4), 0.8)
            self.label(label, px, y0 + self.height * 0.025, anchor="ct", scale=0.8)
        for value, label in yticks:
            if abs(value - x_axis_y) < 1e-10:
                continue
            _, py = p(y_axis_x, value)
            self.line((x0 - 4, py), (x0 + 4, py), 0.8)
            self.label(label, x0 - self.width * 0.014, py, anchor="rc", scale=0.8)
        if kind == "curve":
            count = int(spec.get("samples", max(1200, self.width * 2)))
            if not 100 <= count <= 20000:
                raise ValueError("samples must be between 100 and 20000.")
            xs = np.linspace(self.xlo, self.xhi, count)
            for curve in spec.get("curves", []):
                ys = evaluate_expression(curve["expression"], xs)
                dashed = curve.get("style", "solid") == "dashed"
                if curve.get("style", "solid") not in ("solid", "dashed"):
                    raise ValueError("Curve style must be solid or dashed.")
                pen = max(1, round(self.pen * self.ss * (0.9 if dashed else 1.2)))
                segments, segment = [], []
                for x, y in zip(xs, ys):
                    if math.isfinite(y) and self.ylo <= y <= self.yhi:
                        segment.append(self.point(*p(float(x), float(y))))
                    elif segment:
                        segments.append(segment)
                        segment = []
                if segment:
                    segments.append(segment)
                for segment in segments:
                    if dashed:
                        step = max(8, count // 32)
                        on = max(4, round(step * 0.57))
                        for start in range(0, len(segment), step):
                            self.draw.line(segment[start:start + on], fill=INK, width=pen)
                    elif len(segment) > 1:
                        self.draw.line(segment, fill=INK, width=pen, joint="curve")
        else:
            for item in spec.get("impulses", []):
                x, weight = (item[0], item[1]) if isinstance(item, list) else (item["x"], item["weight"])
                x, weight = float(x), float(weight)
                if not (math.isfinite(x) and math.isfinite(weight)):
                    raise ValueError("Impulse coordinates must be finite.")
                if not (self.xlo <= x <= self.xhi and self.ylo <= weight <= self.yhi):
                    raise ValueError("Impulse falls outside the supplied ranges.")
                self.arrow(p(x, 0.0), p(x, weight))
                label = item.get("label", f"{weight:g}") if isinstance(item, dict) else f"{weight:g}"
                if label:
                    px, py = p(x, weight)
                    self.label(label, px, py + (-self.height * 0.018 if weight >= 0 else self.height * 0.018),
                               anchor="cb" if weight >= 0 else "ct", scale=0.83)
        for label in spec.get("labels", []):
            px, py = p(float(label["x"]), float(label["y"]))
            self.label(label["text"], px, py, anchor=label.get("anchor", "lt"),
                       scale=float(label.get("scale", 0.9)), italic=bool(label.get("italic", False)))
        return self.image.resize((self.width, self.height), Image.Resampling.LANCZOS)


def draw_diagram(spec: dict, font: str | None = None) -> Image.Image:
    panels = spec.get("panels", [])
    if not isinstance(panels, list) or not 1 <= len(panels) <= 36:
        raise ValueError("A diagram requires 1 to 36 panels.")
    width = int(spec.get("width", 1800))
    columns = int(spec.get("columns", 1))
    panel_height = int(spec.get("panel_height", 480))
    gap = int(spec.get("gap", 24))
    supersample = int(spec.get("supersample", 3))
    if not (360 <= width <= 6000 and 1 <= columns <= 6 and 180 <= panel_height <= 3000
            and 0 <= gap <= 200 and 1 <= supersample <= 4):
        raise ValueError("Unsupported diagram dimensions, columns, gap, or supersample.")
    panel_width = (width - gap * (columns - 1)) // columns
    if panel_width < 240:
        raise ValueError("Each panel must be at least 240 pixels wide.")
    rows = math.ceil(len(panels) / columns)
    height = rows * panel_height + (rows - 1) * gap
    if width * height * supersample * supersample > 120_000_000:
        raise ValueError("Diagram exceeds the rendering memory limit; reduce size or supersample.")
    image = Image.new("RGBA", (width, height))
    for index, panel in enumerate(panels):
        rendered = Panel(panel_width, panel_height, supersample, font).render(panel)
        x = (index % columns) * (panel_width + gap)
        y = (index // columns) * (panel_height + gap)
        image.alpha_composite(rendered, (x, y))
    return image


def render_spec(spec: dict, output_dir: Path, font: str | None = None) -> list[Path]:
    diagrams = spec.get("diagrams")
    if not isinstance(diagrams, list) or not diagrams:
        raise ValueError("The root object requires a non-empty diagrams array.")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    files, names = [], set()
    for diagram in diagrams:
        name = diagram.get("name", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", name):
            raise ValueError("Diagram name must be 1-80 filename-safe ASCII characters.")
        name = name.removesuffix(".png")
        path = (output_dir / f"{name}.png").resolve()
        if path.parent != output_dir or path.name in names:
            raise ValueError("Diagram names must be distinct and stay inside output-dir.")
        names.add(path.name)
        draw_diagram(diagram, font).save(path, optimize=True)
        files.append(path)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--font", help="Optional local standard font path.")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
    files = render_spec(spec, args.output_dir, args.font)
    print(json.dumps({"files": [str(path) for path in files]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
