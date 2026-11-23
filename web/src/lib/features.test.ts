import { expect, it, vi } from "vitest";
import { ApiClient } from "./api";
import {
  analysis,
  match,
  improvements,
  draft,
  catalog,
} from "@/test/feature-fixtures";
import { config, id } from "@/test/fixtures";
function setup(data: unknown, status = 200) {
  const fetch = vi
    .fn()
    .mockImplementation(() =>
      Promise.resolve(
        new Response(status === 204 ? null : JSON.stringify(data), { status }),
      ),
    );
  return {
    fetch,
    api: new ApiClient(
      config,
      { getToken: async () => "synthetic-user-token", onUnauthorized: vi.fn() },
      { fetch },
    ),
  };
}
it("serializes real analysis, match and improvement requests and validates reports", async () => {
  const a = setup(analysis);
  expect(await a.api.createAnalysis(id, "A real job description")).toEqual(
    analysis,
  );
  expect(a.fetch.mock.calls[0][1]).toMatchObject({
    method: "POST",
    body: JSON.stringify({ job_description: "A real job description" }),
    headers: {
      Authorization: "Bearer synthetic-user-token",
      "Content-Type": "application/json",
    },
  });
  expect(await setup(match).api.match(id, "Python and Docker")).toEqual(match);
  expect(
    await setup(improvements).api.improve(id, {
      kind: "summary",
      text: "Worked on Python testing.",
      use_ai: false,
    }),
  ).toEqual(improvements);
  expect(await setup(analysis).api.report(id)).toEqual(analysis);
  expect(await setup(match).api.savedMatch(id)).toEqual(match);
});
it("validates owned draft writes, metadata lists and template catalog", async () => {
  const s = setup(draft);
  expect(
    await s.api.saveDraft({ template: draft.template, draft: draft.draft }, id),
  ).toEqual(draft);
  expect(s.fetch.mock.calls[0][1].method).toBe("PUT");
  expect(await setup(catalog).api.templates()).toEqual(catalog);
  expect(await setup(draft).api.draft(id)).toEqual(draft);
  const { draft: privateData, ...metadata } = draft;
  void privateData;
  expect(await setup([metadata]).api.drafts()).toHaveLength(1);
  await expect(setup([draft]).api.drafts()).rejects.toMatchObject({
    code: "invalid_response",
  });
  await expect(
    setup({ ...analysis, raw_text: "private" }).api.report(id),
  ).rejects.toMatchObject({ code: "invalid_response" });
});
it("downloads validated export blobs and rejects unexpected content types", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response("%PDF synthetic", {
        headers: { "Content-Type": "application/pdf" },
      }),
    );
  const api = new ApiClient(
    config,
    { getToken: async () => "synthetic-user-token", onUnauthorized: vi.fn() },
    { fetch },
  );
  expect((await api.exportDraft(id, "pdf")).type).toBe("application/pdf");
  expect(fetch.mock.calls[0][1]).toMatchObject({
    method: "POST",
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
  });
  fetch.mockResolvedValue(
    new Response("provider-error", {
      headers: { "Content-Type": "text/html" },
    }),
  );
  await expect(api.exportDraft(id, "docx")).rejects.toMatchObject({
    code: "invalid_export",
  });
});
it("keeps failed feature writes sanitized and never retries a server failure", async () => {
  const { api, fetch } = setup(
    { detail: "private-secret-provider-message" },
    503,
  );
  await expect(api.createAnalysis(id)).rejects.not.toHaveProperty(
    "message",
    expect.stringContaining("private-secret"),
  );
  expect(fetch).toHaveBeenCalledOnce();
});
