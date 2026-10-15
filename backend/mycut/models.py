from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator, model_validator
from .scene_layout import Id, SceneBlock, validate_blocks


class VisualStyle(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format_id: Literal['editorial', 'radar', 'tutorial', 'impact'] = 'editorial'
    channel_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = 'MYCUT'
    font: Literal['sans', 'serif', 'mono', 'condensed'] | None = None
    google_font: str | None = Field(default=None, min_length=1, max_length=150, exclude_if=lambda value: value is None)
    background: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    text_color: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    media_mode: Literal['animations', 'mixed'] = 'animations'
    image_source: Literal['sources', 'library', 'both'] = 'sources'


class Scene(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Id | None = None
    blocks: list[SceneBlock] | None = Field(default=None, min_length=1, max_length=100)
    title: str = Field(default='', max_length=100)
    narration: str = Field(default='', max_length=1400)
    layout: Literal['flow', 'comparison', 'statement'] = 'flow'
    items: list[str] = Field(default_factory=list, max_length=4)
    image_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    image_fit: Literal['contain', 'cover'] = 'contain'

    @field_validator('blocks')
    @classmethod
    def valid_blocks(cls, value):
        return validate_blocks(value) if value is not None else None

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
    accent_locked: bool = True
    visual_style: VisualStyle | None = None
    ending_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    scenes: list[Scene] = Field(min_length=1, max_length=12)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def unique_scene_ids(self):
        ids = [scene.id for scene in self.scenes if scene.id]
        ids += [block.id for scene in self.scenes for block in scene.blocks or []]
        ids += [block.object.id for scene in self.scenes for block in scene.blocks or [] if block.object]
        if len(ids) != len(set(ids)):
            raise ValueError('Cenas, blocos e objetos devem ter identificações únicas no projeto.')
        if any(scene.blocks is not None and not scene.id for scene in self.scenes):
            raise ValueError('Uma cena com blocos precisa de identificação.')
        return self

    @field_validator('title')
    @classmethod
    def nonempty_title(cls, value):
        if not value.strip():
            raise ValueError('Informe um título.')
        return value.strip()


class CreateProject(BaseModel):
    title: str = Field(default='Novo Short', min_length=1, max_length=100)
    template: Literal['blank'] = 'blank'
    brief: str = Field(default='', max_length=12000)
    automation: Literal['none', 'plan', 'pipeline'] = 'none'
    accent: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    visual_style: VisualStyle | None = None


class ScenePreview(BaseModel):
    scene: Scene
    accent: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
    visual_style: VisualStyle | None = None
    project_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    # Scene time in seconds for animated flows; omitted shows the final state.
    elapsed: float | None = Field(default=None, ge=0, le=180, allow_inf_nan=False)
    width: Literal['preview', 'full'] = 'preview'


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


class AgentCommands(BaseModel):
    model_config = ConfigDict(extra='forbid')
    codex: str = Field(max_length=500)
    claude: str = Field(max_length=500)
    grok: str = Field(max_length=500)


class BrowserSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    chrome_path: str = Field(default='', max_length=500, pattern=r'^[^\x00-\x1f]*$')
    port: int = Field(default=9222, ge=1024, le=65535)


class ModelPrice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input: float = Field(ge=0, le=10_000)
    cache_read: float = Field(ge=0, le=10_000)
    output: float = Field(ge=0, le=10_000)


class PricingSettings(BaseModel):
    """US$ per 1M tokens for CLIs that report no cost, plus the conversions shown next to US$."""
    model_config = ConfigDict(extra='forbid')
    usd_brl: float | None = Field(default=None, gt=0, le=1000)
    elevenlabs_usd_per_1k_credits: float | None = Field(default=None, ge=0, le=1000)
    models: dict[Annotated[str, StringConstraints(pattern=r'^[a-zA-Z0-9._:/-]{1,150}$')], ModelPrice] = Field(max_length=100)


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
    kind: Literal['pipeline', 'plan', 'voice', 'scenes'] = 'pipeline'
    mode: Literal['preview', 'final'] = 'final'
    revision: int = Field(ge=1)


class CoverChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    job_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    image_id: str = Field(pattern=r'^[0-9]{1,2}$')
    revision: int = Field(ge=1)
