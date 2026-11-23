// Only deterministic synthetic test fixtures; no network clients or credentials.
import { account, resume, id } from "../../src/test/fixtures";
import { analysis } from "../../src/test/feature-fixtures";
const state = new URLSearchParams(window.location.search).get("state");
const record = structuredClone(analysis);
record.report.ats.strengths = [
  "Text extracted successfully into a readable document.",
  "Contact information and standard section headings were detected.",
];
record.report.ats.weaknesses = [
  "Review role-specific skills against the target job description.",
  "Several achievement bullets could benefit from measurable context.",
];
record.report.ats.recommendations = [
  "Describe real outcomes and include measurements where your experience supports them.",
  "Review the missing job skills before deciding whether to update your resume.",
];
record.report.ats.writing.grammar = [
  {
    kind: "grammar",
    message: "Review verb agreement",
    context: "The systems works across multiple environments.",
    suggestion: "The systems work across multiple environments.",
  },
];
record.report.ats.writing.weak_phrasings = [
  {
    kind: "weak_phrasings",
    message: "Consider a more specific description",
    context: "Responsible for testing the release.",
    suggestion: "Describe your actual contribution to testing the release.",
  },
];
record.report.ats.writing.repeated_words = [
  ["testing", 4],
  ["development", 3],
  ["supported", 3],
];
if (state === "empty") {
  record.report.ats.writing = {
    spelling: [],
    grammar: [],
    weak_phrasings: [],
    long_sentences: [],
    passive_count: 0,
    buzzwords: [],
    repeated_words: [],
  };
  record.report.impact = { count: 0, bullets: 0 };
  record.report.job_match = null;
  record.report.ats.recommendations = [];
}
const selected = structuredClone(resume);
if (state === "long") {
  record.report.ats.writing.grammar[0].context = "SyntheticLongEvidence".repeat(
    30,
  );
  record.report.ats.recommendations.push(
    "SyntheticLongRecommendation".repeat(20),
  );
}
const rows = [
  { id, resume_id: id, created_at: resume.created_at, ats_score: 72 },
];
const api = {
  resumeAnalyses: async () =>
    state === "initial"
      ? []
      : state === "loading"
        ? new Promise<never>(() => {})
        : rows,
  report: async () => {
    if (state === "error")
      throw new Error("Synthetic report unavailable. Please try again.");
    return record;
  },
  createAnalysis: async () => record,
};
export function useAuth() {
  return { account, api, signOut: async () => {} };
}
export function useWorkspace() {
  return {
    resumes: { data: state === "upload" ? [] : [selected], error: null },
    refresh: async () => {},
    loading: false,
  };
}
