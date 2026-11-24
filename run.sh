#!/bin/sh
set -eu

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
python=${PYTHON:-"$project_dir/.venv/bin/python"}
if [ -z "${PYTHON:-}" ] && [ ! -x "$python" ]; then
    python=python3
fi
exec "$python" -X utf8 "$project_dir/src/cli.py" "$@"
