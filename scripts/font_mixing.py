"""Mix AP and SDT per glyph occurrence, using the same pen for both fonts."""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import random
import string
import unicodedata
import numpy as np
from PIL import Image
from markdown_to_handwrite.config import pt_to_px
from markdown_to_handwrite.handwriting import (
    HandwritingEngine, _character_width, _crop_alpha_with_offset, _has_glyph,
    _load_font, _stable_seed, font_glyph_strokes, render_strokes,
)
from markdown_to_handwrite.typography import westernize_punctuation

DEFAULT_NEW_FONT = Path(__file__).resolve().parents[1] / "assets/fonts/2_APHandwriting.ttf"
NEW_FONT_SYMBOLS = "！@#￥%&*（）-=+【】{}；：’“”《》/\\_^|·~，。"
NEW_FONT_PUNCTUATION = frozenset(NEW_FONT_SYMBOLS + westernize_punctuation(NEW_FONT_SYMBOLS))


def is_mixable_character(char):
    normalized = unicodedata.normalize("NFKC", char)
    if len(normalized) == 1 and normalized in string.ascii_letters + string.digits:
        return True
    code = ord(char)
    han = code == 0x3007 or any(start <= code <= end for start, end in (
        (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
        (0x20000, 0x2FA1F), (0x30000, 0x3347F),
    ))
    return han or char in NEW_FONT_PUNCTUATION


class MixedFontEngine(HandwritingEngine):
    """Stable 50/50 choices, conservative advances, one shared-width renderer."""
    def __init__(self, config, old_engine, dpi, new_font_path=None):
        new_font = Path(new_font_path or DEFAULT_NEW_FONT).resolve(strict=True)
        self.provided_font = str(new_font)
        self.old_engine = old_engine
        # A project copy of AP must never enter the old-font fallback chain.
        for attr in ("font_paths", "math_font_paths"):
            paths = [p for p in getattr(old_engine, attr)
                     if Path(p).resolve() != new_font and Path(p).name != DEFAULT_NEW_FONT.name]
            if not paths:
                raise ValueError("The old-font chain must contain a font other than AP.")
            setattr(old_engine, attr, paths)
        old_engine.font_path = old_engine.font_paths[0]
        old_engine.math_font_path = old_engine.math_font_paths[0]
        settings = deepcopy(config)
        settings.font_path = settings.math_font_path = self.provided_font
        settings.fallback_font_path = old_engine.font_path
        settings.sdt_trajectory_enabled = True
        settings.sdt_width_jitter = settings.sdt_taper = 0
        settings.stroke_weight_variation_sigma_ratio = 0
        settings.second_layer_enabled = False
        settings.sdt_supersample = 6
        super().__init__(settings, reference_size_px=pt_to_px(settings.body_font_pt, dpi),
                         math_reference_size_px=pt_to_px(settings.math_font_pt, dpi))
        self.common_pen_width = old_engine.uniform_pen_width_px()
        self.common_style = replace(old_engine._trajectory_style(), width_jitter=0.0,
                                    taper=0.0, supersample=6)
        self.coverage = {}
        self.counts, self.eligible_counts = Counter(), Counter()
        self.character_counts = defaultdict(Counter)

    def has_provided_glyph(self, char):
        if char not in self.coverage:
            font = _load_font(self.provided_font, 100)
            self.coverage[char] = char.isspace() or (
                _has_glyph(self.provided_font, 100, char)
                and font.getmask(char).getbbox() is not None)
        return self.coverage[char]

    def candidate_paths(self, char, size_px, math_mode=False):
        old_path = self.old_engine._font_path_for_char(char, size_px, math=math_mode)
        old_available = char.isspace() or _has_glyph(old_path, 100, char)
        if is_mixable_character(char) and self.has_provided_glyph(char):
            return (self.provided_font, old_path) if old_available else (self.provided_font,)
        if not old_available:
            raise ValueError(f"The old-font chain has no glyph for {char!r} (U+{ord(char):04X}).")
        return (old_path,)

    def _font_path_for_char(self, char, size_px, math=False):
        return self.candidate_paths(char, size_px, math)[0]

    def character_advance(self, char, size_px, math=False, include_spacing=True):
        # Measurement reserves enough width for either font before choosing.
        width = max(_character_width(path, size_px, char)
                    for path in self.candidate_paths(char, size_px, math))
        if char.isspace():
            return max(size_px * 0.35, width)
        return max(1.0, width + (self.config.word_spacing_px if include_spacing else 0.0))

    def uniform_pen_width_px(self):
        return self.common_pen_width

    def _trajectory_style(self):
        return self.common_style

    def _reference_weight_for_text(self, text, size_px, math_mode=False):
        return self.common_pen_width

    def glyph_raster(self, char, path, size_px, seed):
        font = _load_font(path, size_px)
        bbox = font.getbbox(char)
        if bbox is None:
            raise ValueError(f"Empty visible glyph: {char!r}")
        width, height = max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])
        # AP outlines supply centerlines; the previous font uses SDT strokes.
        strokes = None if path == self.provided_font else self.old_engine.trajectory_store.load(char)
        if strokes is None:
            strokes = font_glyph_strokes(path, char)
        if not strokes:
            raise ValueError(f"Cannot extract visible pen strokes for {char!r}.")
        glyph = render_strokes(strokes, width, height, self.common_pen_width, self.ink,
                               np.random.default_rng(seed), self.common_style, em_size=size_px)
        if glyph.getchannel("A").getbbox() is None:
            raise ValueError(f"Blank visible glyph: {char!r}")
        return glyph, bbox, font

    def _render_with_trajectories(self, text, size_px, max_width, seed, math=False, return_baseline=False):
        positions = random.Random(seed)
        paths = []
        for index, char in enumerate(text):
            candidates = self.candidate_paths(char, size_px, math)
            choice = random.Random(_stable_seed(seed, "font-choice", index, char)).random()
            path = candidates[0] if len(candidates) == 1 or choice < 0.5 else candidates[-1]
            paths.append(path)
            if not char.isspace():
                label = "new" if path == self.provided_font else "old"
                self.counts[label] += 1
                self.character_counts[char][label] += 1
                if len(candidates) == 2:
                    self.eligible_counts[label] += 1
        fonts = [_load_font(path, size_px) for path in paths]
        ascent = max(font.getmetrics()[0] for font in fonts)
        descent = max(font.getmetrics()[1] for font in fonts)
        x_sigma = self._glyph_position_sigma(size_px, self.config.perturb_x_sigma_px)
        y_sigma = self._vertical_position_sigma(size_px, math_mode=math)
        pad = max(round(size_px * 0.4), self._position_jitter_padding(x_sigma, y_sigma))
        height = max(round(size_px * self.config.line_spacing), ascent + descent + 2 * pad)
        image = Image.new("RGBA", (self._line_canvas_width(text, size_px, pad, math), height))
        x, baseline = float(pad), pad + ascent
        for index, (char, path) in enumerate(zip(text, paths)):
            if char.isspace():
                x += self.character_advance(char, size_px, math=math)
                continue
            glyph, bbox, font = self.glyph_raster(char, path, size_px,
                _stable_seed(seed, "uniform-glyph", index, char))
            gx = round(x + bbox[0] + self._sample_position_offset(positions, x_sigma))
            gy = round(baseline - font.getmetrics()[0] + bbox[1]
                       + self._sample_position_offset(positions, y_sigma))
            image.alpha_composite(glyph, (gx, gy))
            x += self._sample_character_advance(char, size_px, positions, math=math)
        cropped, _, top = _crop_alpha_with_offset(image, pad=4)
        return (cropped, round(baseline - top)) if return_baseline else cropped

    def diagnostics(self):
        return {
            "mode": "mixed", "new_font": Path(self.provided_font).name,
            "old_font": Path(self.old_engine.font_path).name,
            "new_probability": 0.5, "seed": self.config.seed,
            "scope": "Latin letters, digits, Han and listed punctuation including normalized ASCII forms",
            "symbols": NEW_FONT_SYMBOLS, "common_pen_width_px": self.common_pen_width,
            "common_pen_style": asdict(self.common_style),
            "rasterized_glyphs": dict(self.counts),
            "eligible_rasterized_glyphs": dict(self.eligible_counts),
            "fonts_by_character": {c: dict(counts) for c, counts in sorted(self.character_counts.items())},
        }
