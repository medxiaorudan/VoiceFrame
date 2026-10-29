"""Create a private GitHub repository and push this source tree using an authenticated gh CLI."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--repository', default='medxiaorudan/voiceframe')
args = p.parse_args()
if not shutil.which('gh'):
    sys.exit('Install GitHub CLI from https://cli.github.com/ then run: gh auth login')
if not shutil.which('git'):
    sys.exit('Install Git first.')
def run(*command):
    return subprocess.run(command, cwd=ROOT, check=True)
run('gh', 'auth', 'status')
if not (ROOT/'.git').exists():
    run('git', 'init', '-b', 'main')
run('git', 'add', '.')
changed = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode
head = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=ROOT, capture_output=True).returncode
if changed or head:
    run('git', 'commit', '-m', 'Build VoiceFrame local-first dubbing studio')
remote = subprocess.run(['git','remote','get-url','origin'],cwd=ROOT,capture_output=True,text=True)
if remote.returncode == 0:
    expected = (f'https://github.com/{args.repository}.git', f'git@github.com:{args.repository}.git')
    if remote.stdout.strip() not in expected:
        sys.exit('Existing origin differs from the requested repository. Inspect it before publishing.')
    run('git', 'push', '-u', 'origin', 'main')
else:
    run('gh', 'repo', 'create', args.repository, '--private', '--source', '.', '--remote', 'origin', '--push',
        '--description', 'Local-first video dubbing studio with Qwen3-TTS, subtitle alignment and reference voices.')
