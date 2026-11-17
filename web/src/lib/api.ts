import { z } from "zod";
import type { PublicConfig } from "./config";
const timestamp = z
  .string()
  .refine((value) => !Number.isNaN(Date.parse(value)));
export const metadataSchema = z
  .object({
    file_name: z.enum(["resume.pdf", "resume.docx"]),
    file_type: z.enum(["pdf", "docx"]),
    pages: z.number().int().nonnegative(),
    word_count: z.number().int().nonnegative(),
    section_order: z.array(z.string()),
    bullet_count: z.number().int().nonnegative(),
    tables_detected: z.number().int().nonnegative(),
    images_detected: z.number().int().nonnegative(),
    headings_look_caps: z.boolean(),
  })
  .strict();
export const resumeSchema = z
  .object({ id: z.uuid(), created_at: timestamp, metadata: metadataSchema })
  .strict();
export const analysisSchema = z
  .object({
    id: z.uuid(),
    created_at: timestamp,
    ats_score: z.number().min(0).max(100).nullable(),
  })
  .strict();
export const historySchema = z
  .object({
    id: z.uuid(),
    created_at: timestamp,
    event: z.string(),
    resource_id: z.uuid(),
  })
  .strict();
export const meSchema = z.object({ id: z.uuid() }).strict();
const downloadSchema = z
  .object({ url: z.string(), expires_in: z.number().int().positive().max(60) })
  .strict();
export type StoredResume = z.infer<typeof resumeSchema>;
export type Analysis = z.infer<typeof analysisSchema>;
export type HistoryEntry = z.infer<typeof historySchema>;
export type Identity = z.infer<typeof meSchema>;
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
const messages: Record<string, string> = {
  unauthorized: "Your session has expired. Please sign in again.",
  unsupported_format: "Choose a PDF or DOCX file.",
  empty_file: "This file is empty.",
  file_too_large: "This file exceeds the upload size limit.",
  invalid_file: "This document could not be read. Choose a valid PDF or DOCX.",
  unsafe_document: "This document could not be accepted safely.",
  not_found: "This document is unavailable or you do not have access.",
  cloud_unavailable:
    "The workspace is temporarily unavailable. Please try again.",
};
function responseError(status: number, body?: unknown): ApiError {
  const code =
    body &&
    typeof body === "object" &&
    "code" in body &&
    typeof body.code === "string"
      ? body.code
      : "request_failed";
  const message =
    status === 401
      ? messages.unauthorized
      : status === 429
        ? "Too many requests. Please wait before trying again."
        : (messages[code] ??
          (status === 403
            ? "You do not have permission for this action."
            : "The request could not be completed. Please try again."));
  return new ApiError(status, code, message);
}
function parse<T>(schema: z.ZodType<T>, body: unknown): T {
  const result = schema.safeParse(body);
  if (!result.success)
    throw new ApiError(
      502,
      "invalid_response",
      "The server returned an unexpected response.",
    );
  return result.data;
}
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export function validateFile(file: File): void {
  if (!/\.(pdf|docx)$/i.test(file.name))
    throw responseError(400, { code: "unsupported_format" });
  if (!file.size) throw responseError(400, { code: "empty_file" });
  if (file.size > MAX_UPLOAD_BYTES)
    throw responseError(400, { code: "file_too_large" });
}
export type TokenSource = {
  getToken: (refresh?: boolean) => Promise<string | null>;
  onUnauthorized: () => void;
};
type Transport = { fetch: typeof fetch; xhr: () => XMLHttpRequest };
export class ApiClient {
  private transport: Transport;
  constructor(
    private config: PublicConfig,
    private auth: TokenSource,
    transport?: Partial<Transport>,
  ) {
    this.transport = {
      fetch: (...args) => fetch(...args),
      xhr: () => new XMLHttpRequest(),
      ...transport,
    };
  }
  private async token(refresh = false): Promise<string> {
    let token: string | null = null;
    try {
      token = await this.auth.getToken(refresh);
    } catch {
      /* Never expose provider errors. */
    }
    if (!token) {
      this.auth.onUnauthorized();
      throw responseError(401);
    }
    return token;
  }
  private async request<T>(
    path: string,
    schema: z.ZodType<T> | null,
    method = "GET",
    signal?: AbortSignal,
  ): Promise<T> {
    for (let attempt = 0; attempt < 2; attempt++) {
      if (signal?.aborted)
        throw new DOMException("Request cancelled", "AbortError");
      const token = await this.token(attempt === 1);
      if (signal?.aborted)
        throw new DOMException("Request cancelled", "AbortError");
      const controller = new AbortController();
      let timedOut = false;
      const cancel = () => controller.abort();
      signal?.addEventListener("abort", cancel, { once: true });
      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, 30000);
      try {
        const response = await this.transport.fetch(this.config.apiUrl + path, {
          method,
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
          credentials: "omit",
          redirect: "error",
          signal: controller.signal,
        });
        if (response.status === 401 && attempt === 0) continue;
        let body: unknown = null;
        if (response.status !== 204) {
          try {
            body = await response.json();
          } catch {
            /* Sanitized below. */
          }
        }
        if (timedOut)
          throw new ApiError(
            0,
            "request_timeout",
            "The request timed out. Refresh your workspace before trying again.",
          );
        if (!response.ok) {
          if (response.status === 401) this.auth.onUnauthorized();
          throw responseError(response.status, body);
        }
        return schema ? parse(schema, body) : (undefined as T);
      } catch (error) {
        if (error instanceof ApiError) throw error;
        if (timedOut)
          throw new ApiError(
            0,
            "request_timeout",
            "The request timed out. Refresh your workspace before trying again.",
          );
        if (
          signal?.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        )
          throw new DOMException("Request cancelled", "AbortError");
        throw new ApiError(
          0,
          "network_error",
          "Could not reach the workspace. Check your connection.",
        );
      } finally {
        clearTimeout(timer);
        signal?.removeEventListener("abort", cancel);
      }
    }
    throw responseError(401);
  }
  me(signal?: AbortSignal) {
    return this.request("/api/me", meSchema, "GET", signal);
  }
  versionedMe(signal?: AbortSignal) {
    return this.request("/api/v1/me", meSchema, "GET", signal);
  }
  private async list<T>(
    path: string,
    schema: z.ZodType<T>,
    signal?: AbortSignal,
  ): Promise<T[]> {
    const all: T[] = [];
    for (let offset = 0; offset < 10000; offset += 100) {
      const batch = await this.request(
        `${path}?offset=${offset}`,
        z.array(schema),
        "GET",
        signal,
      );
      all.push(...batch);
      if (batch.length < 100) return all;
    }
    throw new ApiError(
      0,
      "list_limit",
      "This workspace has too many records to load at once.",
    );
  }
  resumes(signal?: AbortSignal) {
    return this.list("/api/v1/resumes", resumeSchema, signal);
  }
  analyses(signal?: AbortSignal) {
    return this.list("/api/v1/analyses", analysisSchema, signal);
  }
  history(signal?: AbortSignal) {
    return this.list("/api/v1/history", historySchema, signal);
  }
  resume(id: string, signal?: AbortSignal) {
    return this.request(
      `/api/v1/resumes/${z.uuid().parse(id)}`,
      resumeSchema,
      "GET",
      signal,
    );
  }
  analysis(id: string, signal?: AbortSignal) {
    return this.request(
      `/api/v1/analyses/${z.uuid().parse(id)}`,
      analysisSchema,
      "GET",
      signal,
    );
  }
  remove(id: string) {
    return this.request<void>(
      `/api/v1/resumes/${z.uuid().parse(id)}`,
      null,
      "DELETE",
    );
  }
  async download(id: string) {
    const result = await this.request(
      `/api/v1/resumes/${z.uuid().parse(id)}/download`,
      downloadSchema,
      "POST",
    );
    try {
      const url = new URL(result.url);
      if (
        url.origin !== this.config.supabaseUrl ||
        !url.pathname.startsWith("/storage/v1/object/sign/") ||
        url.username ||
        url.password
      )
        throw new Error();
      return { url: url.toString(), expiresIn: result.expires_in };
    } catch {
      throw new ApiError(
        502,
        "unsafe_download",
        "The download link could not be verified.",
      );
    }
  }
  async upload(
    file: File,
    progress: (percent: number) => void,
    signal?: AbortSignal,
  ): Promise<StoredResume> {
    validateFile(file);
    for (let attempt = 0; attempt < 2; attempt++) {
      const token = await this.token(attempt === 1);
      const result = await new Promise<{ status: number; body: unknown }>(
        (resolve, reject) => {
          const xhr = this.transport.xhr();
          const abort = () => xhr.abort();
          const cleanup = () => signal?.removeEventListener("abort", abort);
          if (signal?.aborted) {
            reject(new DOMException("Upload cancelled", "AbortError"));
            return;
          }
          xhr.open("POST", this.config.apiUrl + "/api/v1/resumes");
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
          xhr.timeout = 90000;
          xhr.upload.onprogress = (event) => {
            if (event.lengthComputable)
              progress(
                Math.min(99, Math.round((event.loaded / event.total) * 100)),
              );
          };
          xhr.onload = () => {
            cleanup();
            let body: unknown = null;
            try {
              body = JSON.parse(xhr.responseText);
            } catch {
              /* No response contents in errors. */
            }
            resolve({ status: xhr.status, body });
          };
          xhr.onerror = xhr.ontimeout = () => {
            cleanup();
            reject(
              new ApiError(
                0,
                "upload_uncertain",
                "Upload status is uncertain. Refresh Documents before trying again.",
              ),
            );
          };
          xhr.onabort = () => {
            cleanup();
            reject(new DOMException("Upload cancelled", "AbortError"));
          };
          signal?.addEventListener("abort", abort, { once: true });
          const data = new FormData();
          data.append("file", file);
          xhr.send(data);
        },
      );
      if (result.status === 401 && attempt === 0) continue;
      if (result.status < 200 || result.status >= 300) {
        if (result.status === 401) this.auth.onUnauthorized();
        throw responseError(result.status, result.body);
      }
      const resume = parse(resumeSchema, result.body);
      progress(100);
      return resume;
    }
    throw responseError(401);
  }
}
