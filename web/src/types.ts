export type Scene = {
  title: string;
  narration: string;
  layout: "flow" | "comparison" | "statement";
  items: string[];
  image_id?: string | null;
  image_fit?: "contain" | "cover";
};
export type VisualStyle = {
  format_id: "editorial" | "radar" | "tutorial" | "impact";
  channel_name?: string;
  font: "sans" | "serif" | "mono" | "condensed" | null;
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
  kind: "render" | "pipeline" | "plan" | "voice" | "scenes" | "cover";
  materials: string[];
  steps: { name: string; state: string; message: string; updated_at: number }[];
  output: null | {
    duration: number;
    has_audio: boolean;
    width: number;
    height: number;
    timing: string;
    imported?: boolean;
  };
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
  images?: ProjectImage[];
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
