export function date(value: string, options?: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
    ...options,
  }).format(new Date(value));
}
export function count(value: number) {
  return new Intl.NumberFormat("en").format(value);
}
export function documentTitle(file: {
  metadata: { file_type: string };
  created_at: string;
}) {
  return `Resume ${file.metadata.file_type.toUpperCase()} · ${date(file.created_at)}`;
}
export function safeMessage(error: unknown) {
  // Only our own sanitized API errors reach the UI.
  return error instanceof Error && error.name === "ApiError"
    ? error.message
    : "Something went wrong. Please try again.";
}
