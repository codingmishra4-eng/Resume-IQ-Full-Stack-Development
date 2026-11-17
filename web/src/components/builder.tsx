"use client";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useHydrated } from "@/lib/hydration";
import { z } from "zod";
import { Check, Download, FileJson, Printer } from "lucide-react";
import { Badge, Button, Notice, PageHeading, Panel, useToast } from "./ui";
export const draftSchema = z.object({
  name: z.string().trim().min(1, "Add your name before downloading.").max(150),
  title: z.string().max(200),
  email: z
    .string()
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
});
export type Draft = z.infer<typeof draftSchema>;
const empty: Draft = {
  name: "",
  title: "",
  email: "",
  phone: "",
  location: "",
  summary: "",
  experience: "",
  education: "",
  skills: "",
};
const templates = [
  {
    id: "essential",
    name: "Essential",
    text: "Clear. Focused. Single column.",
  },
  {
    id: "editorial",
    name: "Editorial",
    text: "Classic typography. Quiet confidence.",
  },
  {
    id: "compact",
    name: "Compact",
    text: "A little more room for your story.",
  },
];
export function Builder() {
  const hydrated = useHydrated();
  const [template, setTemplate] = useState("essential");
  const toast = useToast();
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<Draft>({
    defaultValues: empty,
    resolver: zodResolver(draftSchema),
  });
  const values = useWatch({ control }) as Draft;
  function download(draft: Draft) {
    const blob = new Blob(
      [JSON.stringify({ version: 1, template, draft }, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "resumeiq-draft.json";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Draft downloaded. It has not been saved to the cloud.");
  }
  return (
    <>
      <PageHeading
        eyebrow="DESIGN YOUR NEXT CHAPTER"
        title="A story worth presenting well."
        description="Build a clean draft with a live preview. Your edits stay in this browser tab until you download them."
      />
      <Notice>
        Local draft builder · Cloud saving and generated PDF/DOCX exports are
        not connected yet. Refreshing or leaving this page clears unsaved edits.
      </Notice>
      <div className="template-grid" aria-label="Resume templates">
        {templates.map((item) => (
          <button
            type="button"
            key={item.id}
            className={`template-card ${template === item.id ? "selected" : ""}`}
            aria-pressed={template === item.id}
            onClick={() => setTemplate(item.id)}
          >
            <span className={`template-mini ${item.id}`} aria-hidden="true">
              <i />
              <i />
              <hr />
              <i />
              <i />
              <i />
            </span>
            <span>
              <strong>{item.name}</strong>
              <small>{item.text}</small>
            </span>
            {template === item.id && <Check size={17} />}
          </button>
        ))}
      </div>
      <div className="builder-workspace">
        <Panel className="builder-editor">
          <div className="section-heading">
            <h2>Your content</h2>
            <Badge>Draft</Badge>
          </div>
          <form method="post" onSubmit={handleSubmit(download)} noValidate>
            <fieldset className="form-fields" disabled={!hydrated}>
              <div className="field-pair">
                {[
                  ["name", "Full name"],
                  ["title", "Professional title"],
                  ["email", "Email"],
                  ["phone", "Phone"],
                  ["location", "Location"],
                ].map(([key, label]) => (
                  <div className="field" key={key}>
                    <label htmlFor={`builder-${key}`}>{label}</label>
                    <input
                      id={`builder-${key}`}
                      type={key === "email" ? "email" : "text"}
                      {...register(key as keyof Draft)}
                      aria-invalid={Boolean(errors[key as keyof Draft])}
                      aria-describedby={
                        errors[key as keyof Draft]
                          ? `builder-error-${key}`
                          : undefined
                      }
                    />
                    {errors[key as keyof Draft] && (
                      <span className="field-error" id={`builder-error-${key}`}>
                        {errors[key as keyof Draft]?.message}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {[
                ["summary", "Professional summary", 4],
                ["experience", "Experience", 7],
                ["education", "Education", 3],
                ["skills", "Skills", 3],
              ].map(([key, label, rows]) => (
                <div className="field" key={String(key)}>
                  <label htmlFor={`builder-${key}`}>{label}</label>
                  <textarea
                    id={`builder-${key}`}
                    rows={Number(rows)}
                    {...register(key as keyof Draft)}
                  />
                  {errors[key as keyof Draft] && (
                    <span className="field-error">
                      {errors[key as keyof Draft]?.message}
                    </span>
                  )}
                </div>
              ))}
              <Button type="submit">
                <FileJson size={16} /> Download draft JSON
              </Button>
              <p className="muted text-sm mt-3">
                This is editable draft data, not a generated resume PDF.
              </p>
            </fieldset>
          </form>
          <noscript>
            JavaScript is required to edit and download a local draft.
          </noscript>
        </Panel>
        <div className="preview-column">
          <div className="preview-toolbar">
            <div>
              <span className="eyebrow">LIVE PREVIEW</span>
              <span>
                {templates.find((item) => item.id === template)?.name}
              </span>
            </div>
            <Button variant="ghost" onClick={() => window.print()}>
              <Printer size={16} /> Print draft
            </Button>
          </div>
          <article
            className={`resume-preview ${template}`}
            aria-label="Live resume draft preview"
          >
            <header>
              <h2>{values.name || "Your name"}</h2>
              <p className="resume-job-title">
                {values.title || "Your professional title"}
              </p>
              <p className="resume-contact">
                {[values.email, values.phone, values.location]
                  .filter(Boolean)
                  .join(" · ") || "Your contact details"}
              </p>
            </header>
            {[
              ["summary", "Profile"],
              ["experience", "Experience"],
              ["education", "Education"],
              ["skills", "Skills"],
            ].map(([key, label]) => (
              <section key={key}>
                <h3>{label}</h3>
                <p
                  className={
                    !values[key as keyof Draft] ? "preview-placeholder" : ""
                  }
                >
                  {values[key as keyof Draft] ||
                    `Your ${label.toLowerCase()} will appear here.`}
                </p>
              </section>
            ))}
          </article>
          <div className="export-note">
            <Download size={17} />
            <p>
              Use your browser’s print dialog for a local copy. Dedicated
              PDF/DOCX rendering and cloud draft storage need the next
              integration.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
