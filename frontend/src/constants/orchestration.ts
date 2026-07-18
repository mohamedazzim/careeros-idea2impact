export const NODE_NAMES: Record<string, string> = {
  start: "Start",
  resume_agent: "Resume Agent",
  scoring_agent: "Scoring Agent",
  recommendation_agent: "Recommendation Agent",
  reporting_agent: "Reporting Agent",
  opportunity_agent: "Opportunity Agent",
  end: "End",
};

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
