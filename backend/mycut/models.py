from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class Scene(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='', max_length=100)
    narration: str = Field(default='', max_length=1400)
    layout: Literal['flow', 'comparison', 'statement'] = 'flow'
    items: list[str] = Field(default_factory=list, max_length=4)

    @field_validator('narration')
    @classmethod
    def single_paragraph(cls, value):
        return ' '.join(value.split())

    @field_validator('items')
    @classmethod
    def concise_items(cls, values):
        if any(len(value) > 100 for value in values):
            raise ValueError('Cada texto visual pode ter até 100 caracteres.')
        return values


    @model_validator(mode='after')
    def comparison_has_two_sides(self):
        if self.layout == 'comparison' and len(self.items) > 2:
            raise ValueError('Uma comparação pode ter até duas opções.')
        return self


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=5000)
    tags: str = Field(default='', max_length=500)
    sources: str = Field(default='', max_length=8000)
    brief: str = Field(default='', max_length=12000)
    accent: str = Field(default='#c85e37', pattern=r'^#[0-9a-fA-F]{6}$')
    scenes: list[Scene] = Field(min_length=1, max_length=12)
    revision: int = Field(default=0, ge=0)

    @field_validator('title')
    @classmethod
    def nonempty_title(cls, value):
        if not value.strip():
            raise ValueError('Informe um título.')
        return value.strip()


class CreateProject(BaseModel):
    title: str = Field(default='Novo Short', min_length=1, max_length=100)
    template: Literal['blank', 'claude-cloud'] = 'blank'
    brief: str = Field(default='', max_length=12000)
    automation: Literal['none', 'plan', 'pipeline'] = 'none'


class RenderRequest(BaseModel):
    mode: Literal['preview', 'final'] = 'preview'
    revision: int = Field(ge=0)


class AgentChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['codex', 'claude', 'grok']
    model: str = Field(default='', max_length=150, pattern=r'^[a-zA-Z0-9._:/-]*$')


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    research: AgentChoice
    writer: AgentChoice
    director: AgentChoice
    reviewer: AgentChoice


class AgentTestRequest(AgentChoice):
    role: Literal['research', 'writer', 'director', 'reviewer']


class ElevenConnect(BaseModel):
    api_key: SecretStr = Field(min_length=1, max_length=300)


class ElevenSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    voice_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    voice_name: str = Field(default='', max_length=150)
    model_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    stability: float = Field(default=.5, ge=0, le=1)
    similarity_boost: float = Field(default=.75, ge=0, le=1)
    speed: float = Field(default=1, ge=.7, le=1.2)


class AgentRunRequest(BaseModel):
    kind: Literal['pipeline', 'plan', 'voice'] = 'pipeline'
    mode: Literal['preview', 'final'] = 'final'
    revision: int = Field(ge=1)
