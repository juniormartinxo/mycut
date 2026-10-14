export type Scene = {
  title: string;
  narration: string;
  layout: "flow" | "comparison" | "statement";
  items: string[];
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
  kind: "render" | "pipeline" | "plan" | "voice";
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
};
export type Project = {
  id: string;
  title: string;
  description: string;
  tags: string;
  sources: string;
  brief: string;
  accent: string;
  scenes: Scene[];
  revision: number;
  created_at: number;
  updated_at: number;
  jobs: Job[];
  audio?: Material;
  cover?: Material;
  audio_matches_script: boolean;
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
export type Integrations = {
  agents: Record<AgentRole, AgentChoice>;
  agent_models: AgentModelCatalog;
  runner: {
    online: boolean;
    protocol: number;
    providers: Record<AgentChoice["provider"], boolean>;
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
  voices: { id: string; name: string; category: string }[];
  models: { id: string; name: string }[];
};
export type Health = {
  status: string;
  worker_online: boolean;
  ffmpeg: boolean;
};
