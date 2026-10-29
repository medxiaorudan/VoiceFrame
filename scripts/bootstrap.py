"""Cross-platform first-run installation and local server launcher."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--install-engine', action='store_true')
p.add_argument('--no-browser', action='store_true')
p.add_argument('--port', type=int, default=8765)
args = p.parse_args()
if sys.version_info < (3, 11):
    sys.exit('Install Python 3.11 or newer before starting VoiceFrame.')
os.chdir(ROOT)
python = os.environ.get('VOICEFRAME_PYTHON')
if not python:
    env = ROOT/'.venv'
    if not env.exists():
        print('Creating a local Python environment...')
        venv.EnvBuilder(with_pip=True).create(env)
    python = str(env/('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
subprocess.run([python, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
if args.install_engine:
    subprocess.run([python, 'scripts/install_engine.py'], check=True)
for binary in ['ffmpeg', 'ffprobe']:
    if not (shutil.which(binary) or os.getenv(binary.upper()+'_PATH')):
        print(f'NOTE: {binary} is not installed. The UI will open, but media processing needs FFmpeg. See README.')
url = f'http://127.0.0.1:{args.port}'
print(f'VoiceFrame: {url}\nPress Ctrl+C to stop. Projects are saved in ./data.')
if not args.no_browser:
    timer = threading.Timer(3, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()
try:
    subprocess.run([python, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(args.port)], check=True)
except KeyboardInterrupt:
    print('\nVoiceFrame stopped.')
