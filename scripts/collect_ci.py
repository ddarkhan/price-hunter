import os
import subprocess
import sys

mode = 'probe' if os.environ.get('PROBE') == 'true' else 'collect'
raise SystemExit(subprocess.call([sys.executable, '-m', 'collector.runner', mode, '--state-dir', 'runtime/data', '--persist-git']))
