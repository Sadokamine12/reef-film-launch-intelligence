"""Cross-platform setup. Run with Python 3.12 or newer from the extracted folder."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
os.chdir(root)
if sys.version_info<(3,12):
    raise SystemExit('Python 3.12 or newer is required. Install it from python.org.')
node=shutil.which('node')
npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
if not node or not npm:
    raise SystemExit('Install Node.js 22 LTS or newer from nodejs.org, then reopen your terminal.')
major=int(subprocess.check_output([node,'--version'],text=True).strip().lstrip('v').split('.')[0])
if major<22: raise SystemExit('Node.js 22 or newer is required.')
def run(args):
    print('Running:', ' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True)
run([sys.executable,'-m','venv','.venv'])
python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
run([python,'-m','pip','install','-e','apps/api[dev]'])
run([npm,'ci'])
run([npm,'run','typecheck'])
run([npm,'test'])
run([npm,'run','build'])
print('\nSetup complete. Run START_LOCAL.cmd on Windows or ./START_LOCAL.sh on macOS/Linux.')
