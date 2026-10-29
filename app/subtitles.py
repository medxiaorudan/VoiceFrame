import re
from .models import Cue, validate_cues


def timestamp(value):
    parts = value.strip().replace(',', '.').split(':')
    if len(parts) == 2:
        parts.insert(0, '0')
    if len(parts) != 3:
        raise ValueError(f'Invalid subtitle time: {value}')
    h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError('Invalid subtitle time components.')
    return h * 3600 + m * 60 + s


def parse_subtitles(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n').lstrip('\ufeff')
    cues = []
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = block.splitlines()
        if not lines or lines[0].startswith(('WEBVTT', 'NOTE', 'STYLE', 'REGION')):
            continue
        index = next((i for i, line in enumerate(lines) if '-->' in line), None)
        if index is None:
            raise ValueError('Subtitle block has no timestamp.')
        a, b = lines[index].split('-->', 1)
        content = re.sub(r'<[^>]*>', '', '\n'.join(lines[index+1:])).strip()
        cues.append(Cue(id=len(cues)+1, start=timestamp(a), end=timestamp(b.strip().split()[0]), text=content).model_dump())
    if not cues:
        raise ValueError('No subtitle cues found. Upload a UTF-8 SRT or VTT file.')
    if len(cues) > 5000:
        raise ValueError('Maximum 5000 subtitle cues per project.')
    validate_cues(cues)
    return cues


def spoken_text(cue, rules):
    if cue.get('spoken_text', '').strip():
        return cue['spoken_text'].strip()
    mapping = {r['source']: r['replacement'] for r in rules}
    if not mapping:
        return cue['text']
    pattern = '|'.join(re.escape(s) for s in sorted(mapping, key=len, reverse=True))
    return re.sub(pattern, lambda m: mapping[m.group()], cue['text'])


def format_time(value):
    ms = round(value * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def export_srt(cues, offset=0):
    return '\n\n'.join(f"{i+1}\n{format_time(c['start']+offset)} --> {format_time(c['end']+offset)}\n{c['text']}" for i, c in enumerate(cues)) + '\n'
