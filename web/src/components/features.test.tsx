import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Analyzer } from "./analyzer";
import { JobMatch, Improve } from "./workflows";
import { Builder } from "./builder";
import { account, resume, id } from "@/test/fixtures";
import {
  analysis,
  match,
  improvements,
  draft,
  catalog,
} from "@/test/feature-fixtures";
const { api, refresh } = vi.hoisted(() => ({
  api: {
    resumeAnalyses: vi.fn(),
    report: vi.fn(),
    createAnalysis: vi.fn(),
    match: vi.fn(),
    improve: vi.fn(),
    drafts: vi.fn(),
    templates: vi.fn(),
    saveDraft: vi.fn(),
    draft: vi.fn(),
    deleteDraft: vi.fn(),
    exportDraft: vi.fn(),
  },
  refresh: vi.fn(),
}));
vi.mock("./providers", () => ({
  useAuth: () => ({ account, api }),
  useWorkspace: () => ({
    resumes: { data: [resume], error: null },
    refresh,
    loading: false,
  }),
}));
vi.mock("./documents", () => ({
  FileUpload: () => <p>Private file upload</p>,
}));
beforeEach(() => {
  vi.clearAllMocks();
  api.resumeAnalyses.mockResolvedValue([]);
  api.report.mockResolvedValue(analysis);
  api.createAnalysis.mockResolvedValue(analysis);
  api.match.mockResolvedValue(match);
  api.improve.mockResolvedValue(improvements);
  api.drafts.mockResolvedValue([]);
  api.templates.mockResolvedValue(catalog);
  api.saveDraft.mockResolvedValue(draft);
  api.draft.mockResolvedValue(draft);
  api.deleteDraft.mockResolvedValue(undefined);
  refresh.mockResolvedValue(undefined);
});
it("renders all twelve actual report sections and saved report history", async () => {
  const user = userEvent.setup();
  render(<Analyzer />);
  const run = await screen.findByRole("button", { name: "Run analysis" });
  await waitFor(() => expect(run).toBeEnabled());
  await user.click(run);
  expect(
    await screen.findByText("Estimated ATS score: 72.0/100"),
  ).toBeInTheDocument();
  expect(api.createAnalysis).toHaveBeenCalledWith(id, "");
  expect(
    screen
      .getByRole("navigation", { name: "Report sections" })
      .querySelectorAll("a"),
  ).toHaveLength(12);
  await user.click(screen.getByRole("link", { name: "Repeated words" }));
  expect(screen.getByRole("row", { name: "testing 4" })).toBeInTheDocument();
  expect(screen.getByLabelText("Saved analysis history")).toHaveValue(id);
  expect(refresh).toHaveBeenCalled();
});
it("loads persisted reports without creating a new one", async () => {
  api.resumeAnalyses.mockResolvedValue([
    { id, resume_id: id, created_at: resume.created_at, ats_score: 72 },
  ]);
  render(<Analyzer />);
  expect(
    await screen.findByText("Estimated ATS score: 72.0/100"),
  ).toBeInTheDocument();
  expect(api.createAnalysis).not.toHaveBeenCalled();
});
it("keeps the optional job description and selected resume in the existing request", async () => {
  const user = userEvent.setup();
  render(<Analyzer />);
  const run = await screen.findByRole("button", { name: "Run analysis" });
  await waitFor(() => expect(run).toBeEnabled());
  await user.click(screen.getByText("Add a job description"));
  await user.type(
    screen.getByLabelText("Optional job description"),
    "Too short",
  );
  expect(run).toBeDisabled();
  const jd = "Python and Docker engineer needed for a testing project.";
  fireEvent.change(screen.getByLabelText("Optional job description"), {
    target: { value: jd },
  });
  await user.click(run);
  await screen.findByText("Estimated ATS score: 72.0/100");
  expect(api.createAnalysis).toHaveBeenCalledWith(id, jd);
});
it("preserves input and supports retry after an analysis error", async () => {
  api.createAnalysis.mockRejectedValueOnce(new Error("Analysis unavailable."));
  const user = userEvent.setup();
  render(<Analyzer />);
  const run = await screen.findByRole("button", { name: "Run analysis" });
  await waitFor(() => expect(run).toBeEnabled());
  await user.click(run);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Analysis unavailable.",
  );
  expect(screen.getByLabelText("Resume to review")).toHaveValue(id);
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  await user.click(run);
  expect(
    await screen.findByText("Estimated ATS score: 72.0/100"),
  ).toBeInTheDocument();
});
it("compares an owned resume and clears stale results when the input changes", async () => {
  const user = userEvent.setup();
  render(<JobMatch />);
  await user.selectOptions(screen.getByLabelText("Choose your resume"), id);
  fireEvent.change(screen.getByLabelText("Job description"), {
    target: {
      value: "Python and Docker engineer needed for a real testing project.",
    },
  });
  await user.click(screen.getByRole("button", { name: "Compare resumes" }));
  expect(await screen.findByRole("meter")).toHaveAttribute(
    "aria-valuenow",
    "50",
  );
  expect(screen.getByText("Docker")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Job description"), {
    target: { value: "Different role requirements need a new comparison." },
  });
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
});
it("retains user input on errors without showing invented results", async () => {
  api.match.mockRejectedValueOnce(new Error("Workspace unavailable."));
  const user = userEvent.setup();
  render(<JobMatch />);
  await user.selectOptions(screen.getByLabelText("Choose your resume"), id);
  const text = "Python and Docker engineer needed for a real testing project.";
  fireEvent.change(screen.getByLabelText("Job description"), {
    target: { value: text },
  });
  await user.click(screen.getByRole("button", { name: "Compare resumes" }));
  expect(await screen.findByText("Workspace unavailable.")).toBeInTheDocument();
  expect(screen.getByLabelText("Job description")).toHaveValue(text);
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
});
it("shows suggestion provenance and allows reviewing edits without replacing the original", async () => {
  const user = userEvent.setup();
  render(<Improve />);
  await user.selectOptions(screen.getByLabelText("Choose your resume"), id);
  fireEvent.change(screen.getByLabelText("Original summary"), {
    target: { value: improvements.items[0].original },
  });
  await user.click(
    screen.getByRole("button", { name: "Suggest improvements" }),
  );
  expect(await screen.findByText("Rule-based")).toBeInTheDocument();
  const editor = screen.getByLabelText("Review and edit suggestion 1");
  expect(editor).toHaveValue(improvements.items[0].improved);
  await user.type(editor, " Reviewed.");
  expect(screen.getByLabelText("Original summary")).toHaveValue(
    improvements.items[0].original,
  );
  expect(api.improve).toHaveBeenCalledWith(
    id,
    expect.objectContaining({ use_ai: false }),
  );
});
it("saves builder values, loads with confirmation and deletes only the current owned draft", async () => {
  const user = userEvent.setup();
  render(<Builder />);
  await user.type(screen.getByLabelText("Full name"), "Synthetic Candidate");
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Save private draft" }),
    ).toBeEnabled(),
  );
  await user.click(screen.getByRole("button", { name: "Save private draft" }));
  await waitFor(() =>
    expect(api.saveDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        template: "essential",
        draft: expect.objectContaining({ name: "Synthetic Candidate" }),
      }),
      undefined,
    ),
  );
  await user.click(
    screen.getByRole("button", { name: "Delete current saved draft" }),
  );
  expect(
    screen.getByRole("dialog", { name: "Delete saved draft?" }),
  ).toBeInTheDocument();
  expect(api.deleteDraft).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Confirm" }));
  await waitFor(() => expect(api.deleteDraft).toHaveBeenCalledWith(id));
  expect(screen.getByLabelText("Full name")).toHaveValue("");
});
it("loads a private draft only after confirming replacement of local edits", async () => {
  const { draft: content, ...metadata } = draft;
  void content;
  api.drafts.mockResolvedValue([metadata]);
  const user = userEvent.setup();
  render(<Builder />);
  await screen.findByRole("option", { name: /essential ·/ });
  await user.type(
    screen.getByLabelText("Full name"),
    "Unsaved local candidate",
  );
  await user.selectOptions(screen.getByLabelText("Choose a saved draft"), id);
  await user.click(screen.getByRole("button", { name: "Load selected draft" }));
  expect(api.draft).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Full name")).toHaveValue(
    "Unsaved local candidate",
  );
  await user.click(screen.getByRole("button", { name: "Confirm" }));
  await waitFor(() =>
    expect(screen.getByLabelText("Full name")).toHaveValue(
      "Synthetic Candidate",
    ),
  );
  expect(api.draft).toHaveBeenCalledWith(id);
});
it("keeps a saved draft after export failure and downloads a verified blob on retry", async () => {
  api.exportDraft
    .mockRejectedValueOnce(new Error("Export unavailable."))
    .mockResolvedValueOnce(
      new Blob(["%PDF synthetic"], { type: "application/pdf" }),
    );
  const create = vi.fn().mockReturnValue("blob:synthetic-export");
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: create,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  });
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  const user = userEvent.setup();
  render(<Builder />);
  await user.type(screen.getByLabelText("Full name"), "Synthetic Candidate");
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Save and download PDF" }),
    ).toBeEnabled(),
  );
  await user.click(
    screen.getByRole("button", { name: "Save and download PDF" }),
  );
  expect(await screen.findByText("Export unavailable.")).toBeInTheDocument();
  expect(screen.getByLabelText("Full name")).toHaveValue("Synthetic Candidate");
  expect(create).not.toHaveBeenCalled();
  await user.click(
    screen.getByRole("button", { name: "Save and download PDF" }),
  );
  await waitFor(() => expect(create).toHaveBeenCalledOnce());
  expect(click).toHaveBeenCalledOnce();
  expect(api.exportDraft).toHaveBeenCalledWith(id, "pdf");
  click.mockRestore();
});
