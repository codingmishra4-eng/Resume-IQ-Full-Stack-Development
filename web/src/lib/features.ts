import { z } from "zod";
const timestamp = z
  .string()
  .refine((value) => !Number.isNaN(Date.parse(value)));
const check = z
  .object({
    status: z.enum(["pass", "warn", "fail"]),
    label: z.string(),
    detail: z.string(),
  })
  .strict();
const category = z
  .object({
    name: z.string(),
    score: z.number().min(0).max(100),
    weight: z.number(),
    checks: z.array(check),
  })
  .strict();
const issue = z
  .object({
    kind: z.string(),
    message: z.string(),
    context: z.string(),
    suggestion: z.string(),
  })
  .strict();
export const matchResultSchema = z
  .object({
    match_score: z.number().min(0).max(100),
    matching: z.array(z.string()),
    partial: z.array(z.string()),
    missing: z.array(z.string()),
    jd_extra_keywords: z.array(z.string()),
    keyword_matching: z.array(z.string()),
    resume_categories: z.record(z.string(), z.array(z.string())),
    jd_categories: z.record(z.string(), z.array(z.string())),
    notes: z.array(z.string()),
    explanation: z.string(),
  })
  .strict();
export const reportSchema = z
  .object({
    ats: z
      .object({
        overall: z.number().min(0).max(100),
        categories: z.record(z.string(), category),
        strengths: z.array(z.string()),
        weaknesses: z.array(z.string()),
        recommendations: z.array(z.string()),
        writing: z
          .object({
            spelling: z.array(issue),
            grammar: z.array(issue),
            weak_phrasings: z.array(issue),
            long_sentences: z.array(z.string()),
            passive_count: z.number(),
            buzzwords: z.array(z.string()),
            repeated_words: z.array(z.tuple([z.string(), z.number()])),
          })
          .strict(),
      })
      .strict(),
    impact: z.object({ count: z.number(), bullets: z.number() }).strict(),
    sections: z.array(z.string()),
    contact: z.record(z.string(), z.boolean()),
    keywords: z.array(z.string()),
    job_match: matchResultSchema.nullable(),
    template_ids: z.array(z.string()),
    disclaimer: z.string(),
  })
  .strict();
export const analysisRecordSchema = z
  .object({
    id: z.uuid(),
    resume_id: z.uuid(),
    created_at: timestamp,
    report: reportSchema,
  })
  .strict();
export const linkedAnalysisSchema = z
  .object({
    id: z.uuid(),
    resume_id: z.uuid(),
    created_at: timestamp,
    ats_score: z.number().nullable(),
  })
  .strict();
export const matchRecordSchema = z
  .object({
    id: z.uuid(),
    resume_id: z.uuid(),
    created_at: timestamp,
    result: matchResultSchema,
  })
  .strict();
export const improvementsSchema = z
  .object({
    items: z.array(
      z
        .object({
          kind: z.string(),
          original: z.string(),
          improved: z.string(),
          rationale: z.string(),
          source: z.enum(["openai", "rule-based"]),
        })
        .strict(),
    ),
    provider_used: z.boolean(),
    notice: z.string(),
  })
  .strict();
export const builderDraftSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, "Add your name before downloading.")
      .max(150),
    title: z.string().max(200),
    email: z
      .string()
      .max(254)
      .refine(
        (value) => !value || z.email().safeParse(value).success,
        "Enter a valid email or leave it empty.",
      ),
    phone: z.string().max(100),
    location: z.string().max(200),
    summary: z.string().max(5000),
    experience: z.string().max(15000),
    education: z.string().max(5000),
    skills: z.string().max(3000),
  })
  .strict();
export const draftInputSchema = z
  .object({
    template: z.enum(["essential", "editorial", "compact"]),
    draft: builderDraftSchema,
  })
  .strict();
export const draftRecordSchema = draftInputSchema.extend({
  id: z.uuid(),
  created_at: timestamp,
  updated_at: timestamp,
});
export const draftSummarySchema = z
  .object({
    id: z.uuid(),
    template: z.string(),
    created_at: timestamp,
    updated_at: timestamp,
  })
  .strict();
export const templateSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    backend_id: z.string(),
    description: z.string(),
    layout: z.literal("single"),
  })
  .strict();
export type AnalysisRecord = z.infer<typeof analysisRecordSchema>;
export type LinkedAnalysis = z.infer<typeof linkedAnalysisSchema>;
export type MatchRecord = z.infer<typeof matchRecordSchema>;
export type MatchResult = z.infer<typeof matchResultSchema>;
export type Improvements = z.infer<typeof improvementsSchema>;
export type BuilderDraft = z.infer<typeof builderDraftSchema>;
export type DraftInput = z.infer<typeof draftInputSchema>;
export type DraftRecord = z.infer<typeof draftRecordSchema>;
export type DraftSummary = z.infer<typeof draftSummarySchema>;
export type Template = z.infer<typeof templateSchema>;
