import openapi from "@/lib/api/openapi.json";

/** The decoded file-size limit, the same number the server enforces (2 MiB). */
export const MAX_FILE_BYTES = 2 * 1024 * 1024;

/** The schema's limit on the base64 text, read from the API contract. */
export const MAX_BASE64_CHARS: number =
  openapi.components.schemas.UploadSource.properties.content_base64.maxLength;

/** Number of base64 characters needed for `bytes` bytes: 4 for every 3, rounded up. */
export function base64Length(bytes: number): number {
  return 4 * Math.ceil(bytes / 3);
}

/** Base64 of a file's exact bytes. No decoding as text happens here: the server checks UTF-8. */
export async function fileToBase64(file: Blob): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000; // String.fromCharCode takes its arguments on the stack
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

/** A user-facing reason to refuse a file before uploading it, or null if it may be sent. */
export function fileSizeProblem(size: number): string | null {
  if (size > MAX_FILE_BYTES) {
    const mib = (size / (1024 * 1024)).toFixed(1);
    return `This file is ${mib} MiB (${size.toLocaleString("en-GB")} bytes); the limit is 2 MiB (${MAX_FILE_BYTES.toLocaleString("en-GB")} bytes).`;
  }
  return null;
}

/** Missing-value markers as typed in the form: comma-separated, trimmed, blanks dropped. */
export function parseMarkers(text: string): string[] {
  return text
    .split(",")
    .map((m) => m.trim())
    .filter((m) => m !== "");
}
