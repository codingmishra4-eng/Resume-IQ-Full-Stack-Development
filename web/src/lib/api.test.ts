import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, MAX_UPLOAD_BYTES, validateFile } from "./api";
import { config, id, resume } from "@/test/fixtures";
function setup(
  fetch = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify([resume]), { status: 200 })),
) {
  const auth = {
    getToken: vi.fn().mockResolvedValue("synthetic-access-token"),
    onUnauthorized: vi.fn(),
  };
  return { api: new ApiClient(config, auth, { fetch }), auth, fetch };
}
describe("typed FastAPI client", () => {
  it("sends only a bearer user token with no cached data or cookie credentials", async () => {
    const { api, fetch } = setup();
    expect(await api.resumes()).toEqual([resume]);
    expect(fetch).toHaveBeenCalledWith(
      config.apiUrl + "/api/v1/resumes?offset=0",
      expect.objectContaining({
        headers: { Authorization: "Bearer synthetic-access-token" },
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
      }),
    );
  });
  it("loads every bounded list page", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(Array.from({ length: 100 }, () => resume))),
      )
      .mockResolvedValueOnce(new Response("[]"));
    expect(await setup(fetch).api.resumes()).toHaveLength(100);
    expect(fetch.mock.calls[1][0]).toContain("offset=100");
  });
  it("refreshes once after 401 and then uses the refreshed token", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id })));
    const { api, auth } = setup(fetch);
    auth.getToken
      .mockResolvedValueOnce("old-token")
      .mockResolvedValueOnce("fresh-token");
    expect(await api.me()).toEqual({ id });
    expect(auth.getToken.mock.calls).toEqual([[false], [true]]);
    expect(fetch.mock.calls[1][1].headers).toEqual({
      Authorization: "Bearer fresh-token",
    });
  });
  it("rejects expired sessions after one refresh attempt", async () => {
    const { api, auth, fetch } = setup(
      vi
        .fn()
        .mockImplementation(() =>
          Promise.resolve(new Response("{}", { status: 401 })),
        ),
    );
    await expect(api.me()).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(auth.onUnauthorized).toHaveBeenCalledOnce();
  });
  it("never requests an endpoint without a token", async () => {
    const { api, auth, fetch } = setup();
    auth.getToken.mockResolvedValue(null);
    await expect(api.resumes()).rejects.toBeInstanceOf(ApiError);
    expect(fetch).not.toHaveBeenCalled();
    expect(auth.onUnauthorized).toHaveBeenCalled();
  });
  it("rejects extra personal fields and malformed server responses", async () => {
    const { api } = setup(
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify([{ ...resume, raw_text: "PRIVATE" }])),
        ),
    );
    await expect(api.resumes()).rejects.toMatchObject({
      code: "invalid_response",
    });
  });
  it("sanitizes provider error bodies", async () => {
    const { api } = setup(
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ detail: "do-not-echo-provider-data" }),
            { status: 500 },
          ),
        ),
    );
    await expect(api.me()).rejects.not.toHaveProperty(
      "message",
      expect.stringContaining("do-not-echo"),
    );
  });
  it("does not retry uncertain network writes", async () => {
    const { api, fetch } = setup(
      vi.fn().mockRejectedValue(new Error("sensitive transport error")),
    );
    await expect(api.remove(id)).rejects.toMatchObject({
      code: "network_error",
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("keeps permission failures generic and handles empty DELETE responses", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 404 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const { api } = setup(fetch);
    await expect(api.resume(id)).rejects.toMatchObject({ status: 404 });
    await expect(api.remove(id)).resolves.toBeUndefined();
  });
  it.each([
    "https://attacker.invalid/file",
    "javascript:alert(1)",
    config.supabaseUrl + "/other/path",
  ])("rejects an untrusted download target: %s", async (url) => {
    const { api } = setup(
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ url, expires_in: 60 })),
        ),
    );
    await expect(api.download(id)).rejects.toMatchObject({
      code: "unsafe_download",
    });
  });
  it("accepts only expected short-lived Storage download URLs", async () => {
    const url =
      config.supabaseUrl +
      "/storage/v1/object/sign/resumes/synthetic?token=test-only";
    const { api } = setup(
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ url, expires_in: 60 })),
        ),
    );
    await expect(api.download(id)).resolves.toEqual({ url, expiresIn: 60 });
  });
});
describe("file validation and transport", () => {
  it("rejects unsupported, empty and oversized files locally", () => {
    expect(() => validateFile(new File(["x"], "bad.exe"))).toThrow(
      "PDF or DOCX",
    );
    expect(() => validateFile(new File([], "empty.pdf"))).toThrow("empty");
    const large = new File(["x"], "large.pdf");
    Object.defineProperty(large, "size", { value: MAX_UPLOAD_BYTES + 1 });
    expect(() => validateFile(large)).toThrow("size limit");
    expect(() =>
      validateFile(new File(["synthetic"], "RESUME.DOCX")),
    ).not.toThrow();
  });
  it("uses multipart without overriding its boundary and reports byte progress", async () => {
    const handlers: {
      progress?: (event: {
        lengthComputable: boolean;
        loaded: number;
        total: number;
      }) => void;
    } = {};
    const headers = vi.fn();
    const xhr = {
      upload: {
        set onprogress(
          value: (event: {
            lengthComputable: boolean;
            loaded: number;
            total: number;
          }) => void,
        ) {
          handlers.progress = value;
        },
      },
      open: vi.fn(),
      setRequestHeader: headers,
      timeout: 0,
      responseText: JSON.stringify(resume),
      status: 201,
      onload: () => {},
      onerror: () => {},
      ontimeout: () => {},
      onabort: () => {},
      abort: vi.fn(),
      send: vi.fn((data: FormData) => {
        expect(data.get("file")).toBeInstanceOf(File);
        handlers.progress?.({ lengthComputable: true, loaded: 50, total: 100 });
        xhr.onload();
      }),
    };
    const progress = vi.fn();
    const auth = {
      getToken: vi.fn().mockResolvedValue("synthetic-token"),
      onUnauthorized: vi.fn(),
    };
    const api = new ApiClient(config, auth, {
      xhr: () => xhr as unknown as XMLHttpRequest,
    });
    expect(
      await api.upload(new File(["fake PDF"], "resume.pdf"), progress),
    ).toEqual(resume);
    expect(headers.mock.calls).toEqual([
      ["Authorization", "Bearer synthetic-token"],
    ]);
    expect(progress.mock.calls).toEqual([[50], [100]]);
  });
});
it("does not retry an upload when its outcome is uncertain", async () => {
  const xhr = {
    upload: {},
    open: vi.fn(),
    setRequestHeader: vi.fn(),
    timeout: 0,
    ontimeout: () => {},
    send: vi.fn(() => xhr.ontimeout()),
  };
  const factory = vi.fn(() => xhr as unknown as XMLHttpRequest);
  const api = new ApiClient(
    config,
    { getToken: async () => "synthetic-token", onUnauthorized: vi.fn() },
    { xhr: factory },
  );
  await expect(
    api.upload(new File(["fake PDF"], "resume.pdf"), vi.fn()),
  ).rejects.toMatchObject({ code: "upload_uncertain" });
  expect(factory).toHaveBeenCalledOnce();
});
it("bounds stalled requests and does not retry on timeout", async () => {
  vi.useFakeTimers();
  try {
    const fetch = vi.fn(
      (_url: unknown, options: RequestInit) =>
        new Promise<Response>((_resolve, reject) =>
          options.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          ),
        ),
    );
    const { api } = setup(fetch);
    const result = expect(api.me()).rejects.toMatchObject({
      code: "request_timeout",
    });
    await vi.advanceTimersByTimeAsync(30001);
    await result;
    expect(fetch).toHaveBeenCalledOnce();
  } finally {
    vi.useRealTimers();
  }
});
