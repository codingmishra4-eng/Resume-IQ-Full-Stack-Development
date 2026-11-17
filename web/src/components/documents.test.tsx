import { expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  DownloadButton,
  DeleteButton,
  FileUpload,
  DocumentsPage,
} from "./documents";
import { ToastProvider } from "./ui";
import { account, config, resume } from "@/test/fixtures";
import { ApiError } from "@/lib/api";
const mocks = vi.hoisted(() => ({
  upload: vi.fn(),
  download: vi.fn(),
  remove: vi.fn(),
  refresh: vi.fn(),
}));
vi.mock("./providers", () => ({
  useAuth: () => ({ api: mocks, account }),
  useWorkspace: () => ({
    resumes: { data: [resume], error: null },
    analyses: { data: [], error: null },
    history: { data: [], error: null },
    loading: false,
    refresh: mocks.refresh,
  }),
}));
it("uploads a validated file and refreshes documents after success", async () => {
  mocks.upload.mockImplementation(async (file, progress) => {
    progress(50);
    return resume;
  });
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <FileUpload />
    </ToastProvider>,
  );
  await user.upload(
    screen.getByLabelText("Choose a PDF or DOCX resume"),
    new File(["synthetic pdf"], "test.pdf"),
  );
  await user.click(screen.getByRole("button", { name: "Upload resume" }));
  await waitFor(() => expect(mocks.upload).toHaveBeenCalled());
  expect(mocks.refresh).toHaveBeenCalled();
  expect(
    await screen.findByText("Resume uploaded to your private workspace."),
  ).toBeInTheDocument();
});
it("reports upload errors without claiming persistence succeeded", async () => {
  mocks.upload.mockRejectedValue(
    new ApiError(400, "invalid_file", "This document could not be read."),
  );
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <FileUpload />
    </ToastProvider>,
  );
  await user.upload(
    screen.getByLabelText("Choose a PDF or DOCX resume"),
    new File(["corrupt"], "bad.pdf"),
  );
  await user.click(screen.getByRole("button", { name: "Upload resume" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "could not be read",
  );
  expect(screen.queryByText(/Resume uploaded to/)).not.toBeInTheDocument();
});
it("requires explicit confirmation before deleting and then refreshes", async () => {
  mocks.remove.mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <DeleteButton resume={resume} />
    </ToastProvider>,
  );
  await user.click(screen.getByRole("button", { name: /Delete PDF/ }));
  expect(mocks.remove).not.toHaveBeenCalled();
  expect(
    screen.getByRole("dialog", { name: "Delete this resume?" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Delete resume" }));
  await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith(resume.id));
  expect(mocks.refresh).toHaveBeenCalled();
});
it("prepares a short-lived, no-referrer download only after a click", async () => {
  mocks.download.mockResolvedValue({
    url:
      config.supabaseUrl +
      "/storage/v1/object/sign/resumes/test?token=synthetic",
    expiresIn: 60,
  });
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <DownloadButton resume={resume} />
    </ToastProvider>,
  );
  expect(mocks.download).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: /Download PDF/ }));
  const link = await screen.findByRole("link", { name: /Save PDF/ });
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(link).toHaveAttribute("referrerPolicy", "no-referrer");
  expect(link.getAttribute("href")).toContain("download=resume.pdf");
});
it("filters real documents without inventing rows and supports the history view", async () => {
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <DocumentsPage />
    </ToastProvider>,
  );
  expect(screen.getByText("resume.pdf")).toBeInTheDocument();
  await user.type(screen.getByPlaceholderText("Search documents…"), "no-match");
  expect(screen.getByText("No documents match.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Activity" }));
  expect(screen.getByText("A clean slate.")).toBeInTheDocument();
});
