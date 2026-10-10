import json
import os
import datetime as dt
import time
from pathlib import Path
from .engine import timestamp


def read_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding='utf-8-sig'))


def atomic_json(path, data):
    path = Path(path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') == content:
        return False
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8', newline='\n') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(4):
        try:
            os.replace(str(temp), str(path))
            break
        except PermissionError:
            if attempt == 3:
                raise
            time.sleep(.2 * (attempt + 1))
    return True


class Lock:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(self.fd, str(os.getpid()).encode())
        return self

    def __exit__(self, *args):
        os.close(self.fd)
        self.path.unlink()


def record(state, offer, now, days):
    item = state['items'].setdefault(offer['id'], {'offer': offer, 'history': []})
    identity_fields = ('sku', 'variant', 'quantity', 'volume', 'bundle', 'condition')
    if any(item['offer'].get(k) != offer.get(k) for k in identity_fields):
        item['history'] = []  # A changed variant/pack is a new time series.
    cutoff = now - dt.timedelta(days=days)
    history = [h for h in item['history'] if timestamp(h['at']) >= cutoff]
    sample = {k: offer.get(k) for k in ('price', 'struck_price', 'available')}
    from .engine import total
    sample.update(at=offer['observed_at'], total=total(offer), url=offer['url'])
    if not history or any(history[-1].get(k) != sample[k] for k in ('price', 'struck_price', 'available', 'total')) or (now - timestamp(history[-1]['at'])).total_seconds() >= 86400:
        history.append(sample)
    item['history'] = history[-240:]
    item['offer'] = offer
    return item['history']
