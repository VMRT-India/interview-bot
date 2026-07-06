export type InterviewType = "TECHNICAL" | "BEHAVIORAL" | "HR";
export type SessionStatus = "ACTIVE" | "COMPLETED" | "ABANDONED";

export interface User {
  id: string;
  email: string | null;
  phone_number: string | null;
  is_alpha_tester: boolean;
  is_guest: boolean;
  has_password: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface SessionRead {
  id: string;
  user_id: string;
  interview_type: InterviewType;
  status: SessionStatus;
  started_at: string;
  ended_at: string | null;
  total_score: number | null;
  llm_provider: string | null;
  target_minutes: number | null;
  has_resume: boolean;
}

export interface ScoreRead {
  id: string;
  session_id: string;
  turn_number: number;
  score: number;
  correctness: number;
  depth: number;
  communication: number;
  strengths: string;
  weaknesses: string;
  improvement: string;
  created_at: string;
}

export interface SessionDetail extends SessionRead {
  overall_summary: string | null;
  top_strengths: string[];
  key_gaps: string[];
  recommendations: string[];
  hire_signal: string | null;
  turn_scores: ScoreRead[];
}

export interface FinalReport {
  session_id: string;
  total_score: number;
  overall_summary: string;
  top_strengths: string[];
  key_gaps: string[];
  recommendations: string[];
  hire_signal: string;
  turn_scores: ScoreRead[];
}

export interface UserAPIKeyRead {
  id: string;
  provider: string;
  model_name: string | null;
  base_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformStats {
  total_users: number;
  total_sessions: number;
  completed_sessions: number;
  avg_score: number | null;
}

/** Messages sent from the server over WS /ws/interview/{id} */
export type ServerWsMessage =
  | { type: "token"; content: string }
  | { type: "question_end" }
  | { type: "session_end"; content: string }
  | { type: "error"; content: string };
