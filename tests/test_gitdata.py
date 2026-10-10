import os
import tempfile
import unittest
from pathlib import Path
from collector.gitdata import git, prepare, commit
from collector.state import atomic_json, read_json


class GitPersistenceTests(unittest.TestCase):
    def test_two_independent_runner_checkouts_recover_history_and_ledger(self):
        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote, source = root / 'remote.git', root / 'source'
            git(['init', '--bare', str(remote)])
            git(['init', str(source)])
            git(['config', 'user.name', 'test'], source)
            git(['config', 'user.email', 'test@example.invalid'], source)
            (source / 'source.txt').write_text('test source', encoding='utf-8')
            git(['add', '.'], source)
            git(['commit', '-m', 'initial'], source)
            git(['remote', 'add', 'origin', str(remote)], source)
            git(['push', '-u', 'origin', 'HEAD'], source)
            try:
                os.chdir(str(source))
                data = prepare('runtime/first')
                state = {'items': {'sku-1': {'history': [{'price': 40000}]}}, 'notifications': {'sku-1': {'pending': True, 'sent': False}}}
                atomic_json(data / 'state.json', state)
                atomic_json(data / 'catalog.json', {'offers': []})
                commit(data)
                second = prepare('runtime/second')
                self.assertEqual(read_json(second / 'state.json', {}), state)
                self.assertFalse((data / 'source.txt').exists())
                self.assertTrue((source / 'source.txt').exists())
                state['notifications']['sku-1'].update(pending=False, sent=True)
                atomic_json(second / 'state.json', state)
                commit(second)
                third = prepare('runtime/third')
                self.assertTrue(read_json(third / 'state.json', {})['notifications']['sku-1']['sent'])
                # A stale writer is rejected by fast-forward push, never overwrites ledger.
                stale = dict(state, stale_writer=True)
                atomic_json(data / 'state.json', stale)
                with self.assertRaises(RuntimeError):
                    commit(data)
            finally:
                os.chdir(str(previous_cwd))


if __name__ == '__main__':
    unittest.main()
