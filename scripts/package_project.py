"""Create a source archive without dependencies, local state, credentials or caches."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.cache', 'node_modules', 'dist', 'runtime', '__pycache__', '.venv', '.pytest_cache'}


if __name__ == '__main__':
    target = ROOT / 'price-hunter.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in ROOT.rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in EXCLUDED for part in relative.parts):
                continue
            if path.suffix in ('.zip', '.log', '.pyc', '.tmp') or path.name.endswith('.tsbuildinfo'):
                continue
            if path.name.startswith('.env') and path.name != '.env.example':
                continue
            z.write(path, str(Path('price-hunter') / relative))
    print('Архив проекта готов: price-hunter.zip (%s bytes)' % target.stat().st_size)
