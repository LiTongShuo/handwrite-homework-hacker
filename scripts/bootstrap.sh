#!/usr/bin/env sh
set -eu
skill_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work_dir=${1:-"$PWD"}
python_bin=${PYTHON:-python3}
mkdir -p "$work_dir"
venv_dir="$work_dir/.notability-venv"
if [ ! -x "$venv_dir/bin/python" ]; then
  "$python_bin" -m venv "$venv_dir"
fi
"$venv_dir/bin/python" -c "import sys; assert sys.version_info[:2] == (3,12), 'Use CPython 3.12.'"
if ! "$venv_dir/bin/python" -m pip install --no-cache-dir --no-index --find-links "$skill_dir/wheelhouse" -r "$skill_dir/requirements.txt"; then
  if [ "${NOTABILITY_ALLOW_DOWNLOAD:-0}" != "1" ]; then
    echo 'Offline wheels target CPython 3.12 / Windows x64. Set NOTABILITY_ALLOW_DOWNLOAD=1 for this platform.' >&2
    exit 1
  fi
  "$venv_dir/bin/python" -m pip install --no-cache-dir -r "$skill_dir/requirements.txt"
fi
if [ -n "${NOTABILITY_ASSETS_FROM:-}" ]; then
  "$venv_dir/bin/python" "$skill_dir/scripts/restore_assets.py" --from-repository "$NOTABILITY_ASSETS_FROM"
else
  "$venv_dir/bin/python" "$skill_dir/scripts/restore_assets.py" --download
fi
"$venv_dir/bin/python" "$skill_dir/scripts/doctor.py"
printf 'NOTABILITY_PYTHON=%s\n' "$venv_dir/bin/python"
