import math
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Cue(BaseModel):
    id: int = Field(ge=1)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    text: str = Field(min_length=1, max_length=2000)
    spoken_text: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def ordered(self):
        if self.end <= self.start or not self.text.strip():
            raise ValueError('Cue end must follow start; text cannot be blank.')
        return self


class Rule(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    replacement: str = Field(min_length=1, max_length=300)


class Settings(BaseModel):
    engine: Literal['auto', 'mlx', 'torch'] = 'auto'
    mode: Literal['preset', 'reference'] = 'preset'
    speaker: Literal['Dylan', 'Uncle_Fu', 'Ryan', 'Aiden', 'Vivian', 'Serena', 'Eric'] = 'Dylan'
    language: Literal['Chinese', 'English', 'Auto'] = 'Chinese'
    instruction: str = Field(default='Explain naturally to a student, with a clear, conversational delivery.', max_length=1000)
    reference_text: str = Field(default='', max_length=3000)
    seed: int = Field(default=42, ge=0, le=2147483647)
    offset: float = Field(default=0, ge=-60, le=60, allow_inf_nan=False)
    max_speed: float = Field(default=1.15, ge=1, le=3, allow_inf_nan=False)
    rules: list[Rule] = Field(default_factory=list, max_length=100)


class ProjectEdit(BaseModel):
    revision: int
    name: str = Field(min_length=1, max_length=120)
    cues: list[Cue] = Field(default_factory=list, max_length=5000)
    settings: Settings = Field(default_factory=Settings)

    @model_validator(mode='after')
    def validate_cues(self):
        validate_cues([c.model_dump() for c in self.cues])
        sources = [r.source for r in self.settings.rules]
        if len(sources) != len(set(sources)):
            raise ValueError('Pronunciation rules must have unique source phrases.')
        return self


class JobRequest(BaseModel):
    kind: Literal['voice', 'preview', 'final', 'extract', 'ocr', 'transcribe']
    revision: int
    text: str = Field(default='我们先看一个简单的例子。理解了这一步，后面的计算就容易了。', min_length=1, max_length=500)
    start: float = Field(default=0, ge=0, allow_inf_nan=False)
    duration: float = Field(default=30, ge=3, le=7200, allow_inf_nan=False)
    stream_index: int = Field(default=0, ge=0, le=100)
    crop_top: float = Field(default=.75, ge=0, le=.95, allow_inf_nan=False)
    crop_bottom: float = Field(default=1, gt=0, le=1, allow_inf_nan=False)
    interval: float = Field(default=.5, ge=.2, le=3, allow_inf_nan=False)

    @model_validator(mode='after')
    def crop(self):
        if self.crop_bottom <= self.crop_top:
            raise ValueError('Crop bottom must exceed crop top.')
        return self


def validate_cues(cues):
    previous, ids = 0, set()
    for cue in cues:
        if not all(math.isfinite(cue[k]) for k in ('start', 'end')):
            raise ValueError('Cue timestamps must be finite.')
        if cue['start'] < previous - .0001 or cue['end'] <= cue['start']:
            raise ValueError(f"Cue {cue['id']} overlaps or has invalid times.")
        if cue['id'] in ids:
            raise ValueError('Duplicate cue ID.')
        previous = cue['end']
        ids.add(cue['id'])

