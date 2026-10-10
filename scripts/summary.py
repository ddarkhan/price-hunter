import json
import os
from pathlib import Path

p = Path('runtime/data/catalog.json')
if p.exists():
    data = json.loads(p.read_text(encoding='utf-8'))
    lines = ['## Price Hunter', 'Проверено товаров: %s. Это частичный охват.' % data['coverage']['checked'], '', '| Источник | Статус | Проверено |', '| --- | --- | --- |']
    lines += ['| %s | %s | %s |' % (s['shop'], s['status'], s['products_checked']) for s in data['sources']]
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    else:
        print('\n'.join(lines))
