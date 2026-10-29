import gc
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import numpy as np
import soundfile as sf


def engine_name(requested='auto'):
    if requested != 'auto':
        return requested
    return 'mlx' if platform.system() == 'Darwin' and platform.machine() == 'arm64' else 'torch'


def available(module):
    return importlib.util.find_spec(module) is not None


def model_id(settings):
    variant = 'Base' if settings['mode'] == 'reference' else 'CustomVoice'
    if engine_name(settings['engine']) == 'mlx':
        return f'mlx-community/Qwen3-TTS-12Hz-1.7B-{variant}-4bit'
    return f'Qwen/Qwen3-TTS-12Hz-1.7B-{variant}'


def audio_key(text, settings, reference_hash=None, attempt=0):
    # Timing, alignment and dictionary changes that leave spoken text unchanged reuse audio.
    voice = {k: settings[k] for k in ('mode', 'speaker', 'language', 'instruction', 'reference_text', 'seed')}
    if settings['mode'] == 'reference':
        voice.pop('speaker')
        voice.pop('instruction')
    else:
        voice.pop('reference_text')
    payload = [text, voice, model_id(settings), engine_name(settings['engine']), reference_hash, attempt]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Synthesizer:
    def __init__(self):
        self.loaded = None
        self.model = None

    def synthesize(self, text, settings, reference, destination, attempt=0):
        engine = engine_name(settings['engine'])
        mid = model_id(settings)
        if engine == 'mlx' and not (platform.system() == 'Darwin' and platform.machine() == 'arm64'):
            raise RuntimeError('MLX requires an Apple Silicon Mac. Select Auto or PyTorch on Windows/Linux.')
        if engine == 'mlx' and not available('mlx_audio'):
            raise RuntimeError('MLX-Audio is not installed. Run: python scripts/install_engine.py --engine mlx')
        if engine == 'torch' and not available('qwen_tts'):
            raise RuntimeError('Qwen TTS is not installed. Run: python scripts/install_engine.py --engine torch')
        if settings['mode'] == 'reference' and (reference is None or not settings['reference_text'].strip()):
            raise ValueError('Upload reference audio and its exact transcript first.')
        if self.loaded != (engine, mid):
            self.model = None
            gc.collect()
            if available('torch'):
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            if engine == 'mlx':
                from mlx_audio.tts.utils import load_model
                self.model = load_model(mid)
            else:
                import torch
                from qwen_tts import Qwen3TTSModel
                cuda = torch.cuda.is_available()
                self.model = Qwen3TTSModel.from_pretrained(mid, device_map='cuda:0' if cuda else 'cpu',
                    dtype=torch.bfloat16 if cuda and torch.cuda.is_bf16_supported() else torch.float32,
                    attn_implementation='sdpa')
            self.loaded = (engine, mid)
        if engine == 'mlx':
            import mlx.core as mx
            mx.random.seed(settings['seed'] + attempt)
            if settings['mode'] == 'reference':
                results = self.model.generate(text=text, ref_audio=str(reference), ref_text=settings['reference_text'])
            else:
                results = self.model.generate_custom_voice(text=text, speaker=settings['speaker'],
                    language=settings['language'], instruct=settings['instruction'])
            chunks, rate = [], None
            for result in results:
                if rate is not None and rate != result.sample_rate:
                    raise RuntimeError('Audio sample rate changed unexpectedly.')
                rate = int(result.sample_rate)
                chunks.append(np.asarray(result.audio, dtype=np.float32).reshape(-1))
            if not chunks:
                raise RuntimeError('The model returned no audio.')
            audio = np.concatenate(chunks)
        else:
            import torch
            torch.manual_seed(settings['seed'] + attempt)
            with torch.inference_mode():
                if settings['mode'] == 'reference':
                    wavs, rate = self.model.generate_voice_clone(text=text, language=settings['language'],
                        ref_audio=str(reference), ref_text=settings['reference_text'])
                else:
                    wavs, rate = self.model.generate_custom_voice(text=text, language=settings['language'],
                        speaker=settings['speaker'], instruct=settings['instruction'])
            audio = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
        if not audio.size or not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-7:
            raise RuntimeError('The model returned invalid or silent audio.')
        audio *= min(1., .98/np.max(np.abs(audio)))
        temporary = Path(destination).with_suffix('.partial.wav')
        sf.write(str(temporary), audio, rate, subtype='PCM_16')
        temporary.replace(destination)
