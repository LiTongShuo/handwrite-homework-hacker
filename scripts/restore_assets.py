"""Restore verified upstream font/trajectory assets without redistributing them."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verified(path, item):
    return (path.is_file() and path.stat().st_size == item['bytes'] and
            hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-repository', type=Path)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'assets/asset-sources.json').read_text(encoding='utf-8'))
    vendor = (ROOT / 'vendor/MarkdownToHandwrite').resolve()
    restored = []
    for item in manifest['assets']:
        target = (vendor / item['path']).resolve()
        target.relative_to(vendor)
        if verified(target, item):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        local = args.from_repository / item['path'] if args.from_repository else None
        if local and verified(local, item):
            shutil.copyfile(local, target)
            restored.append({'path': item['path'], 'source': 'local'})
            continue
        if not args.download:
            raise FileNotFoundError(f"Missing verified asset: {item['path']}. Supply --from-repository or --download.")
        if not item['url'].startswith('https://raw.githubusercontent.com/lyc07/MarkdownToHandwrite/'):
            raise ValueError('Unexpected asset download source.')
        partial = target.with_suffix(target.suffix + '.part')
        with urllib.request.urlopen(item['url'], timeout=30) as source, partial.open('wb') as output:
            shutil.copyfileobj(source, output)
        if not verified(partial, item):
            partial.unlink(missing_ok=True)
            raise ValueError(f"Asset digest mismatch: {item['path']}")
        partial.replace(target)
        restored.append({'path': item['path'], 'source': 'upstream'})
    print(json.dumps({'status': 'ok', 'restored': restored}, ensure_ascii=False))


if __name__ == '__main__':
    main()
