"""Install the platform-specific speech backend into the current Python environment."""
import argparse
import platform
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--engine', choices=['auto', 'mlx', 'torch'], default='auto')
p.add_argument('--asr', action='store_true')
args = p.parse_args()
engine = args.engine
if engine == 'auto':
    engine = 'mlx' if platform.system() == 'Darwin' and platform.machine() == 'arm64' else 'torch'
if engine == 'mlx' and not (platform.system() == 'Darwin' and platform.machine() == 'arm64'):
    p.error('MLX requires native Apple Silicon Python. Choose torch on Windows/Linux.')
if platform.system() == 'Darwin' and platform.machine() != 'arm64':
    p.error('Intel Mac support is deferred. Version 0.1 targets Apple Silicon, Windows and Linux.')
packages = ['mlx-audio>=0.3,<1'] if engine == 'mlx' else ['qwen-tts>=0.1,<1']
if args.asr:
    packages.append('faster-whisper>=1,<2')
subprocess.run([sys.executable, '-m', 'pip', 'install', *packages], check=True)
print('Engine installed. Model weights download on the first generation request.')
if engine == 'torch':
    import torch
    print('CUDA available:', torch.cuda.is_available())
    if not torch.cuda.is_available():
        print('CPU mode is slow. For NVIDIA GPUs, install the matching PyTorch build from https://pytorch.org/get-started/locally/')
