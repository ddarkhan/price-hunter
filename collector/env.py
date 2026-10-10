"""Minimal ignored .env reader. No shell expansion, never logs values."""
import os
from pathlib import Path


def load_env():
    p = Path('.env')
    if not p.is_file():
        return
    for line in p.read_text(encoding='utf-8-sig').splitlines():
        if '=' not in line or line.strip().startswith('#'):
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'):
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)
