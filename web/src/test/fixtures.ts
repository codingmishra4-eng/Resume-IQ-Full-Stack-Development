import type { StoredResume } from "@/lib/api";
export const id = "11111111-1111-4111-8111-111111111111";
export const config = {
  apiUrl: "http://127.0.0.1:8000",
  supabaseUrl: "https://synthetic.supabase.co",
  publishableKey: "sb_publishable_unit_test_only",
};
export const resume: StoredResume = {
  id,
  created_at: "2026-11-18T08:30:00Z",
  metadata: {
    file_name: "resume.pdf",
    file_type: "pdf",
    pages: 2,
    word_count: 450,
    section_order: ["summary", "skills"],
    bullet_count: 8,
    tables_detected: 0,
    images_detected: 0,
    headings_look_caps: true,
  },
};
export const account = {
  id,
  email: "synthetic@example.invalid",
  createdAt: "2026-11-18T08:30:00Z",
};
