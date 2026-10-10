"""Durable data branch, ordinary fast-forward push; never force-push."""
import argparse
import subprocess
from pathlib import Path

BRANCH = 'price-data'


def git(args, cwd=None, check=True):
    result = subprocess.run(['git'] + args, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if check and result.returncode:
        # Never print git's stderr: remote URLs might contain authentication data.
        raise RuntimeError('Операция Git не удалась: ' + args[0])
    return result


def prepare(path):
    workspace = Path.cwd().resolve()
    path = Path(path)
    path = (path if path.is_absolute() else workspace / path).resolve()
    if workspace not in path.parents:
        raise RuntimeError('Каталог ветки данных должен находиться внутри текущего проекта')
    if path.exists():
        raise RuntimeError('Каталог состояния уже существует; используйте чистый runner')
    git(['worktree', 'prune'])
    remote = git(['ls-remote', '--heads', 'origin', BRANCH]).stdout.strip()
    if remote:
        git(['fetch', 'origin', BRANCH])
        git(['worktree', 'add', '--detach', str(path), 'FETCH_HEAD'])
    else:
        git(['worktree', 'add', '--detach', str(path), 'HEAD'])
        git(['checkout', '--orphan', BRANCH], path)
        git(['rm', '-rf', '--ignore-unmatch', '.'], path)
    git(['config', 'user.name', 'price-hunter[bot]'], path)
    git(['config', 'user.email', 'price-hunter@users.noreply.github.com'], path)
    # Checkout credentials are scoped to the source worktree. Copy only config,
    # never print/store the token in tracked files.
    key = 'http.https://github.com/.extraheader'
    header = git(['config', '--get', key], check=False)
    if header.returncode == 0:
        git(['config', '--worktree', key, header.stdout.strip()], path, check=False)
    return path


def commit(path):
    path = Path(path).resolve()
    git(['add', '--', 'state.json', 'catalog.json'], path)
    changed = git(['diff', '--cached', '--quiet'], path, check=False).returncode != 0
    if not changed:
        return
    git(['commit', '-m', 'Update public observations and notification ledger'], path)
    git(['push', 'origin', 'HEAD:refs/heads/' + BRANCH], path)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['prepare', 'commit'])
    p.add_argument('--path', default='runtime/data')
    a = p.parse_args()
    (prepare if a.command == 'prepare' else commit)(a.path)
