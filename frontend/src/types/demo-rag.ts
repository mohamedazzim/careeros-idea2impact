export interface DemoRagChatRequest {
  session_id: string;
  question: string;
  viewer_role: string;
  top_k: number;
}

export interface DemoRagCitation {
  doc_name: string;
  section_title: string;
  source_path: string;
  score: number;
}

export interface DemoRagError {
  code: string;
  message: string;
}

export interface DemoRagChatResponse {
  status: string;
  answer: string;
  confidence: number;
  citations: DemoRagCitation[];
  follow_up_questions: string[];
  needs_verification: boolean;
  error?: DemoRagError | null;
}

export type RagChatRole = "user" | "assistant";

export interface RagChatMessage {
  id: string;
  role: RagChatRole;
  content: string;
  createdAt: number;
  confidence?: number;
  citations?: DemoRagCitation[];
  followUpQuestions?: string[];
  needsVerification?: boolean;
  error?: DemoRagError | null;
  pending?: boolean;
}

export type RagPanelState = "closed" | "open" | "minimized" | "maximized";

