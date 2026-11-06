"""Check this portable skill's packages, template, font and SDT assets."""
from __future__ import annotations
import importlib
import importlib.metadata
import json
import sys
from pathlib import Path
from restore_assets import verified

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.prefix == sys.base_prefix:
        raise RuntimeError('Run doctor.py inside a virtual environment created by bootstrap.')
    for package in ('PIL', 'numpy', 'markdown_it', 'mdit_py_plugins', 'reportlab'):
        importlib.import_module(package)
    sys.path.insert(0, str(ROOT / 'vendor/MarkdownToHandwrite/src'))
    from markdown_to_handwrite.config import ReportConfig
    from markdown_to_handwrite.handwriting import HandwritingEngine
    template = ROOT / 'assets/notability-template.png'
    font = ROOT / 'vendor/MarkdownToHandwrite/font/1_SDT.ttf'
    if not template.is_file() or not font.is_file():
        raise FileNotFoundError('Bundled template or handwriting font is missing.')
    assets = json.loads((ROOT / 'assets/asset-sources.json').read_text(encoding='utf-8'))
    for item in assets.get('bundled_user_assets', []):
        target = (ROOT / item['path']).resolve()
        target.relative_to(ROOT.resolve())
        if not verified(target, item):
            raise FileNotFoundError(f"Missing or changed bundled font: {item['path']}")
    config = ReportConfig()
    config.handwriting.font_path = str(font)
    engine = HandwritingEngine(config.handwriting)
    if not engine.uses_sdt_trajectories:
        raise RuntimeError('Bundled SDT handwriting trajectories are unavailable.')
    print(json.dumps({'status': 'ok', 'python': sys.version.split()[0],
                      'skill': str(ROOT), 'sdt': True, 'mixed_font': '2_APHandwriting.ttf',
                      'packages': {p: importlib.metadata.version(p) for p in
                                   ('numpy', 'pillow', 'markdown-it-py', 'mdit-py-plugins', 'reportlab')}},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
