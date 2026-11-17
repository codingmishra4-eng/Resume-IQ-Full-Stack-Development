import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dashboard } from "./dashboard";
import { JobMatch, Improve } from "./workflows";
import { Builder } from "./builder";
import { Modal } from "./ui";
import { account, resume } from "@/test/fixtures";
vi.mock("./providers", () => ({
  useAuth: () => ({ account, api: {} }),
  useWorkspace: () => ({
    resumes: { data: [resume], error: null },
    analyses: { data: [], error: null },
    history: { data: [], error: null },
    loading: false,
    refresh: () => {},
  }),
}));
it("shows real document counts and no fabricated ATS score", () => {
  render(<Dashboard />);
  expect(screen.getByText("Uploaded resumes")).toBeInTheDocument();
  expect(
    screen.getByText("A little perspective goes a long way."),
  ).toBeInTheDocument();
  expect(screen.getByText("resume.pdf")).toBeInTheDocument();
  expect(screen.queryByText(/98%/)).not.toBeInTheDocument();
});
it("keeps job matching explicitly unavailable while accepting a local draft", async () => {
  const user = userEvent.setup();
  render(<JobMatch />);
  await user.type(
    screen.getByLabelText("Job description"),
    "Synthetic role requirements",
  );
  expect(
    screen.getByRole("button", { name: /Compare resumes/ }),
  ).toBeDisabled();
  expect(screen.getByText("Not generated")).toBeInTheDocument();
  expect(screen.getByLabelText("Job description")).toHaveValue(
    "Synthetic role requirements",
  );
});
it("keeps independent writing drafts without inventing a rewrite", async () => {
  const user = userEvent.setup();
  render(<Improve />);
  await user.type(
    screen.getByLabelText("Original summary"),
    "My original summary",
  );
  await user.click(screen.getByRole("button", { name: "Experience bullets" }));
  expect(screen.getByLabelText("Original bullet points")).toHaveValue("");
  await user.click(
    screen.getByRole("button", { name: "Professional summary" }),
  );
  expect(screen.getByLabelText("Original summary")).toHaveValue(
    "My original summary",
  );
  expect(
    screen.getByText("No rewrite has been generated."),
  ).toBeInTheDocument();
});
it("edits a real local builder preview and changes template presentation", async () => {
  const user = userEvent.setup();
  render(<Builder />);
  await user.type(screen.getByLabelText("Full name"), "Synthetic Candidate");
  await user.type(
    screen.getByLabelText("Professional summary"),
    "A truthful local draft.",
  );
  expect(
    screen.getByRole("article", { name: "Live resume draft preview" }),
  ).toHaveTextContent("Synthetic Candidate");
  expect(screen.getByRole("article")).toHaveTextContent(
    "A truthful local draft.",
  );
  await user.click(screen.getByRole("button", { name: /Editorial/ }));
  expect(screen.getByRole("article")).toHaveClass("editorial");
  expect(
    screen.getByText(
      /Cloud saving and generated PDF\/DOCX exports are not connected/,
    ),
  ).toBeInTheDocument();
});
it("provides accessible modal semantics, Escape dismissal and focus return", async () => {
  const close = vi.fn();
  const user = userEvent.setup();
  const { rerender } = render(
    <>
      <button>Trigger</button>
      <Modal open={false} title="Confirm" onClose={close}>
        Content
      </Modal>
    </>,
  );
  screen.getByRole("button", { name: "Trigger" }).focus();
  rerender(
    <>
      <button>Trigger</button>
      <Modal open title="Confirm" onClose={close}>
        Content
      </Modal>
    </>,
  );
  expect(screen.getByRole("dialog", { name: "Confirm" })).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(close).toHaveBeenCalledOnce();
  rerender(
    <>
      <button>Trigger</button>
      <Modal open={false} title="Confirm" onClose={close}>
        Content
      </Modal>
    </>,
  );
  expect(screen.getByRole("button", { name: "Trigger" })).toHaveFocus();
});
it("downloads validated draft JSON without claiming cloud persistence", async () => {
  const create = vi
    .fn<(blob: Blob) => string>()
    .mockReturnValue("blob:synthetic-draft");
  const revoke = vi.fn();
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: create,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: revoke,
  });
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  const user = userEvent.setup();
  render(<Builder />);
  await user.type(screen.getByLabelText("Full name"), "Synthetic Candidate");
  await user.click(screen.getByRole("button", { name: "Download draft JSON" }));
  expect(create).toHaveBeenCalledOnce();
  expect(click).toHaveBeenCalledOnce();
  const blob = create.mock.calls[0][0] as unknown as Blob;
  const content = await new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob);
  });
  expect(JSON.parse(content)).toMatchObject({
    version: 1,
    template: "essential",
    draft: { name: "Synthetic Candidate" },
  });
  click.mockRestore();
});
it("keeps personal builder fields disabled on the server-rendered form", async () => {
  const { renderToString } = await import("react-dom/server");
  const html = renderToString(<Builder />);
  expect(html).toContain('method="post"');
  expect(html).toContain('disabled=""');
  expect(html).toContain("JavaScript is required");
});
