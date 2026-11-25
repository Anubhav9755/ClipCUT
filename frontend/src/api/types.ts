export type VideoStatus = "queued" | "processing" | "done" | "failed";

export interface Clip {
  id: number;
  rank: number;
  title: string;
  approved: number;
  render_status: string;
  post_status: string;
  post_url: string;
}

export interface Video {
  id: string;
  filename: string;
  status: VideoStatus;
  stage: string;
  progress: number;
  error: string | null;
  created_at: number; // epoch seconds
  duration: number | null;
  meta: { video?: { width?: number; height?: number } };
  clips: Clip[];
}

export interface AppStatus { ai_key: boolean }
export interface YouTubeStatus { connected: boolean }
