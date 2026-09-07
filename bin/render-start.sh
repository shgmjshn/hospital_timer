#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate --noinput
python manage.py seed_masters
python manage.py ensure_operators

# gunicorn 25.1.0 は control socket を先に立てると worker が起動せず、
# 待受はしていても HTTP に応答しない（画面が読み込み中のままになる）。
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --timeout 60 \
  --no-control-socket \
  --access-logfile - \
  --error-logfile -
