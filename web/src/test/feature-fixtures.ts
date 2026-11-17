import { id, resume } from "./fixtures";
import type {
  AnalysisRecord,
  MatchRecord,
  Improvements,
  DraftRecord,
} from "@/lib/features";
export const match: MatchRecord = {
  id,
  resume_id: id,
  created_at: resume.created_at,
  result: {
    match_score: 50,
    matching: ["Python"],
    partial: [],
    missing: ["Docker"],
    jd_extra_keywords: ["delivery"],
    keyword_matching: ["testing"],
    resume_categories: { Programming: ["Python"] },
    jd_categories: { Programming: ["Python"], DevOps: ["Docker"] },
    notes: ["Only add skills you genuinely have."],
    explanation:
      "Synthetic deterministic test evidence: one exact skill out of two.",
  },
};
export const analysis: AnalysisRecord = {
  id,
  resume_id: id,
  created_at: resume.created_at,
  report: {
    ats: {
      overall: 72,
      categories: {
        readability: {
          name: "Readability",
          score: 80,
          weight: 0.2,
          checks: [
            {
              status: "pass",
              label: "Readable text",
              detail: "Extracted successfully",
            },
          ],
        },
        structure: { name: "Structure", score: 60, weight: 0.2, checks: [] },
        completeness: {
          name: "Completeness",
          score: 60,
          weight: 0.2,
          checks: [],
        },
        keywords: { name: "Keywords", score: 70, weight: 0.2, checks: [] },
        contact: { name: "Contact", score: 90, weight: 0.1, checks: [] },
        formatting: { name: "Formatting", score: 90, weight: 0.1, checks: [] },
      },
      strengths: ["Readable text"],
      weaknesses: ["Review skills"],
      recommendations: ["Describe real outcomes."],
      writing: {
        spelling: [],
        grammar: [],
        weak_phrasings: [],
        long_sentences: [],
        passive_count: 0,
        buzzwords: [],
        repeated_words: [["testing", 4]],
      },
    },
    impact: { count: 2, bullets: 8 },
    sections: ["summary", "skills"],
    contact: { email: true, phone: false, linkedin: false },
    keywords: ["Python"],
    job_match: match.result,
    template_ids: ["essential", "editorial", "compact"],
    disclaimer: "Estimated heuristic, not official certification.",
  },
};
export const improvements: Improvements = {
  provider_used: false,
  notice: "Review source-grounded suggestions.",
  items: [
    {
      kind: "summary",
      original: "Worked on Python testing.",
      improved: "Contributed to Python testing.",
      rationale: "Conservative edit, no new claims.",
      source: "rule-based",
    },
  ],
};
export const draft: DraftRecord = {
  id,
  created_at: resume.created_at,
  updated_at: resume.created_at,
  template: "essential",
  draft: {
    name: "Synthetic Candidate",
    title: "Engineer",
    email: "",
    phone: "",
    location: "",
    summary: "Real experience.",
    experience: "Built real software.",
    education: "",
    skills: "Python",
  },
};
export const catalog = [
  {
    id: "essential",
    name: "Essential",
    backend_id: "ats-minimal",
    description: "Single column",
    layout: "single" as const,
  },
];
