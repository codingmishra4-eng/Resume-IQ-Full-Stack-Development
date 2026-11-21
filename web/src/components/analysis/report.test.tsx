import { expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AnalysisReport, ReportLoading } from "./report";
import { analysis } from "@/test/feature-fixtures";
import { resume } from "@/test/fixtures";

async function expand(id: string) {
  const section = document.getElementById(
    `report-${id}`,
  )! as HTMLDetailsElement;
  if (!section.open)
    await userEvent.setup().click(section.querySelector("summary")!);
  return section;
}

it("keeps the overview and useful summaries visible without expanding the whole report", async () => {
  render(<AnalysisReport record={analysis} resume={resume} />);
  expect(
    screen.getByRole("heading", { name: "Resume overview" }),
  ).toBeVisible();
  expect(document.querySelectorAll(".ar-section[open]")).toHaveLength(2);
  expect(document.getElementById("report-parseability")).toHaveAttribute(
    "open",
  );
  expect(document.getElementById("report-recommendations")).toHaveAttribute(
    "open",
  );
  expect(document.getElementById("report-grammar")).not.toHaveAttribute("open");
  const section = await expand("grammar");
  expect(
    within(section).getByText("No grammar issues flagged by these checks."),
  ).toBeVisible();
});

it("shows actual scores, category weights and check evidence", async () => {
  const user = userEvent.setup();
  render(<AnalysisReport record={analysis} resume={resume} />);
  expect(
    screen.getByRole("meter", { name: "Estimated ATS score" }),
  ).toHaveAttribute("aria-valuenow", "72");
  const category = screen.getByText("Readability").closest("details")!;
  await user.click(category.querySelector("summary")!);
  expect(within(category).getByText("20% weight")).toBeVisible();
  expect(within(category).getByText("Extracted successfully")).toBeVisible();
  expect(within(category).getByText("Pass")).toBeVisible();
  await expand("impact");
  await expand("repetition");
  expect(
    screen.getByRole("meter", {
      name: "Bullets containing quantified evidence",
    }),
  ).toHaveAttribute("aria-valuenow", "2");
  expect(screen.getByRole("row", { name: "testing 4" })).toBeVisible();
  expect(screen.getByText(/Counts only. Contextual replacement/)).toBeVisible();
  expect(screen.getByText(/no priority ranking was supplied/)).toBeVisible();
});

it("reopens a collapsed section from report navigation and moves keyboard focus", async () => {
  const user = userEvent.setup();
  render(<AnalysisReport record={analysis} resume={resume} />);
  const section = document.getElementById(
    "report-repetition",
  )! as HTMLDetailsElement;
  expect(section.open).toBe(false);
  await user.click(
    within(
      screen.getByRole("navigation", { name: "Report sections" }),
    ).getByRole("link", { name: "Repeated words" }),
  );
  expect(section.open).toBe(true);
  expect(section.querySelector("summary")).toHaveFocus();
  expect(screen.getByRole("link", { name: "Repeated words" })).toHaveAttribute(
    "aria-current",
    "location",
  );
});

it("keeps original writing evidence and suggested edits distinct", () => {
  const record = structuredClone(analysis);
  record.report.ats.writing.grammar = [
    {
      kind: "grammar",
      message: "Review verb agreement",
      context: "The systems works.",
      suggestion: "The systems work.",
    },
  ];
  render(<AnalysisReport record={record} resume={resume} />);
  expect(screen.getByText("The systems works.").tagName).toBe("BLOCKQUOTE");
  expect(screen.getByText("The systems work.")).toBeVisible();
  expect(screen.getByText("1 writing finding")).toBeVisible();
  expect(
    screen.getByText("No spelling issues flagged by these checks."),
  ).toBeVisible();
});

it("shows honest empty states and avoids a zero-denominator impact meter", async () => {
  const record = structuredClone(analysis);
  record.report.impact = { count: 0, bullets: 0 };
  record.report.ats.writing.repeated_words = [];
  record.report.job_match = null;
  record.report.ats.recommendations = [];
  render(<AnalysisReport record={record} resume={resume} />);
  for (const id of [
    "impact",
    "repetition",
    "grammar",
    "skills",
    "match",
    "recommendations",
  ])
    await expand(id);
  expect(document.getElementById("report-repetition")).toHaveClass(
    "ar-section-compact",
  );
  expect(document.querySelectorAll(".ar-writing-group-empty")).toHaveLength(3);
  expect(
    screen.queryByRole("meter", {
      name: "Bullets containing quantified evidence",
    }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText("No bullet points were detected for this check."),
  ).toBeVisible();
  expect(
    screen.getByText(
      "No repeated terms were flagged by the word-frequency check.",
    ),
  ).toBeVisible();
  expect(
    screen.getByText(
      "A role description is needed to identify job-specific gaps.",
    ),
  ).toBeVisible();
  expect(
    screen.getByText(
      "No additional recommendations were returned by this analysis.",
    ),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "Open Job Match" })).toHaveAttribute(
    "href",
    "/job-match",
  );
});

it("announces loading without fake progress or completed processing stages", () => {
  render(<ReportLoading creating />);
  expect(screen.getByRole("status")).toHaveTextContent("Analyzing your resume");
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).not.toHaveTextContent(/\d+%/);
});

it("lets keyboard users choose a mobile destination before explicitly opening it", async () => {
  const user = userEvent.setup();
  render(<AnalysisReport record={analysis} resume={resume} />);
  const select = screen.getByLabelText("Jump to report section");
  expect(within(select).getAllByRole("option")).toHaveLength(12);
  await user.selectOptions(select, "repetition");
  expect(select).toHaveFocus();
  expect(document.getElementById("report-repetition")).not.toHaveAttribute(
    "open",
  );
  await user.tab();
  expect(
    screen.getByRole("button", { name: "Go to selected report section" }),
  ).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(document.getElementById("report-repetition")).toHaveAttribute("open");
  expect(document.querySelector("#report-repetition > summary")).toHaveFocus();
});
