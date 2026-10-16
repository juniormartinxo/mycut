export type Scene = {
  id?: string | null;
  blocks?: SceneBlock[] | null;
  title: string;
  narration: string;
  layout: "flow" | "comparison" | "statement";
  items: string[];
  image_id?: string | null;
  image_fit?: "contain" | "cover";
  // The first plano is the scene's own composition; later planos change it in time (ADR 0004).
  background?: Background | null;
  brand?: boolean;
  shots?: Shot[];
};
export type Motion = "none" | "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "pan_up" | "pan_down";
export type Background = {
  kind: "color" | "gradient" | "image" | "video";
  color?: string | null;
  color_to?: string | null;
  angle?: number;
  asset_id?: string | null;
  zoom?: number;
  crop_x?: number;
  crop_y?: number;
  motion?: Motion;
  dim?: number;
};
export type Shot = {
  id: string;
  anchor: string | null;
  transition: "cut" | "fade";
  background: Background | null;
  brand: boolean;
  blocks: SceneBlock[];
};
export type ShotWindow = { id: string; start: number; end: number };
export type VisualStyle = {
  format_id: "editorial" | "radar" | "tutorial" | "impact";
  channel_name?: string;
  font: "sans" | "serif" | "mono" | "condensed" | null;
  google_font?: string | null;
  background: string | null;
  text_color: string | null;
  media_mode: "animations" | "mixed";
  image_source: "sources" | "library" | "both";
};
export type ShortFormat = {
  id: VisualStyle["format_id"];
  name: string;
  description: string;
  use_case: string;
  font: NonNullable<VisualStyle["font"]>;
  background: string;
  text_color: string;
  accent: string;
  preview_url: string;
};
export type ProjectImage = {
  id: string;
  name: string;
  url: string;
  width: number;
  height: number;
  source_url: string;
  page_url: string;
};
export type Job = {
  id: string;
  project_id: string;
  mode: "preview" | "final";
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  message: string;
  revision: number;
  created_at: number;
  kind: "render" | "pipeline" | "plan" | "voice" | "scenes" | "cover" | "scene_edit";
  materials: string[];
  steps: { name: string; state: string; message: string; updated_at: number }[];
  output: null | {
    duration: number;
    has_audio: boolean;
    width: number;
    height: number;
    timing: string;
    imported?: boolean;
    has_narration?: boolean;
    ending?: (Omit<EndingClip, "url" | "poster_url"> & { start_seconds: number; total_duration: number }) | null;
  };
};
export type EndingClip = {
  id: string;
  name: string;
  duration: number;
  width: number;
  height: number;
  has_audio: boolean;
  url: string;
  poster_url: string;
};
export type Material = {
  name: string;
  url: string;
  sha256: string;
  duration?: number;
  script_hash?: string;
  /** "<message id>/<image id>" when the cover was chosen in the cover chat. */
  chat_image?: string;
};
export type Project = {
  id: string;
  title: string;
  description: string;
  tags: string;
  sources: string;
  brief: string;
  accent: string;
  accent_locked?: boolean;
  visual_style?: VisualStyle | null;
  ending_id?: string | null;
  images?: ProjectImage[];
  videos?: ProjectVideo[];
  image_notes?: string[];
  scenes: Scene[];
  revision: number;
  created_at: number;
  updated_at: number;
  jobs: Job[];
  audio?: Material;
  cover?: Material;
  audio_matches_script: boolean;
  usage_total: UsageTotal;
};

export type FlowChart = {
  kind: "bars" | "line" | "gauge";
  values: number[];
  labels: string[];
  maximum: number | null;
  unit: string;
};
export type FlowNode = {
  id: string;
  label: string;
  icon: string | null;
  shape: "circle" | "rounded" | "diamond";
  x: number;
  y: number;
  size: number;
  chart: FlowChart | null;
};
export type FlowSpec = {
  nodes: FlowNode[];
  links: { source: string; target: string }[];
  steps: { source: string | null; target: string; kind: "request" | "result"; anchor: string | null }[];
};
export type VisualObject = {
  id: string;
  type: "title" | "paragraph" | "image" | "video" | "flow";
  width: number;
  height: number;
  horizontal: "left" | "center" | "right";
  vertical: "top" | "center" | "bottom";
  text: string;
  font: string | null;
  font_size: number;
  color: string | null;
  align: "left" | "center" | "right";
  text_vertical?: "top" | "center" | "bottom";
  asset_id: string | null;
  fit: "contain" | "cover";
  zoom: number;
  crop_x: number;
  crop_y: number;
  flow?: FlowSpec | null;
  reveal?: "none" | "lines" | "typing";
  motion?: Motion;
};
export type SceneBlock = {
  id: string;
  width: number;
  height: number;
  align: "left" | "center" | "right";
  object: VisualObject | null;
};
export type ProjectVideo = {
  id: string;
  name: string;
  url: string;
  poster_url: string;
  width: number;
  height: number;
  duration: number;
};
export type SceneIssue = {
  object_id: string | null;
  shot_id?: string;
  kind: "missing_media" | "overflow" | "missing_flow" | "anchor" | "shot_anchor" | "shot_short";
  message: string;
  font_size?: number | null;
  step?: number;
};
export type SceneClock = { duration: number; source: "narration" | "estimate" | "export" };
export type SceneThread = {
  id: string;
  scene_id: string;
  scope: "scene" | "block" | "object";
  target_id: string;
  marked: boolean;
  resolved: boolean;
  archived: boolean;
};
export type SceneMessage = {
  id: string;
  thread_id: string;
  text: string;
  created_at: number;
  state: Job["state"];
  status: string;
  stale: boolean;
  decision: "accepted" | "discarded" | null;
  reply: string;
  blocks: SceneBlock[] | null;
};
export type UsageTotal = {
  input: number;
  cache_read: number;
  cache_write: number;
  output: number;
  reasoning: number;
  web_searches: number;
  credits: number;
  usd: number;
  unpriced: number;
};
export type UsageCall = {
  step: "research" | "writer" | "director" | "reviewer" | "voice" | "cover";
  attempt: number;
  provider: AgentChoice["provider"] | "elevenlabs";
  requested_model: string;
  model: string;
  state: "running" | "succeeded" | "failed" | "interrupted";
  created_at: number;
  input: number;
  cache_read: number;
  cache_write: number;
  output: number;
  reasoning: number;
  web_searches: number;
  credits: number | null;
  credits_estimated?: boolean;
  usd: number | null;
  cost_source: "cli" | "tabela" | "plano" | null;
  unreported?: boolean;
};
export type ProjectUsage = {
  total: UsageTotal;
  usd_brl: number | null;
  checked_at: string;
  source: string;
  versions: {
    id: string;
    kind: Job["kind"];
    state: Job["state"];
    created_at: number;
    recorded: boolean;
    calls: UsageCall[];
    total: UsageTotal;
  }[];
};
export type Pricing = {
  usd_brl: number | null;
  elevenlabs_usd_per_1k_credits: number | null;
  checked_at?: string;
  models: Record<string, { input: number; cache_read: number; output: number }>;
};
export type AgentRole = "research" | "writer" | "director" | "reviewer";
export type AgentChoice = {
  provider: "codex" | "claude" | "grok";
  model: string;
};
export type AgentModelCatalog = Record<
  AgentChoice["provider"],
  {
    models: { id: string; name: string }[];
    checked_at: number | null;
    source: string;
    error: string;
  }
>;
export type AgentTest = AgentChoice & {
  id: string;
  role: AgentRole;
  state:
    | "queued"
    | "running"
    | "cancelling"
    | "cancelled"
    | "expired"
    | "failed"
    | "succeeded";
  created_at: number;
  reply: string;
  reported_models: string[];
  verification: "unknown" | "match" | "resolved" | "mismatch";
  error: string;
  elapsed: number | null;
};
export type BrowserSettings = {
  enabled: boolean;
  chrome_path: string;
  port: number;
};
export type Integrations = {
  agents: Record<AgentRole, AgentChoice>;
  commands: Record<AgentChoice["provider"], string>;
  browser: BrowserSettings;
  pricing: Pricing;
  browser_test: {
    id: string;
    checked_at: number;
    version: string;
    error: string;
  } | null;
  agent_models: AgentModelCatalog;
  runner: {
    online: boolean;
    protocol: number;
    providers: Record<AgentChoice["provider"], boolean>;
    browser: { enabled: boolean; available: boolean; version: string };
  };
  elevenlabs: {
    connected: boolean;
    voice_id: string;
    voice_name: string;
    model_id: string;
    stability: number;
    similarity_boost: number;
    speed: number;
  };
};
export type VoiceCatalog = {
  voices: {
    id: string;
    name: string;
    category: string;
    preview_url?: string | null;
    language?: string | null;
    accent?: string | null;
  }[];
  models: { id: string; name: string }[];
};
export type VoiceTest = {
  id: string;
  text: string;
  settings: Omit<Integrations["elevenlabs"], "connected" | "voice_name">;
  voice_name: string;
  model_name: string;
  created_at: number;
  duration: number;
  cached: boolean;
  url: string;
};
export type Health = {
  status: string;
  worker_online: boolean;
  ffmpeg: boolean;
};
export type CoverMessage = {
  id: string;
  created_at: number;
  state: Job["state"];
  status: string;
  provider: AgentChoice["provider"];
  model: string;
  text: string;
  attachments: { name: string; url: string }[];
  reply: string;
  images: { id: string; url: string; width: number; height: number }[];
};
