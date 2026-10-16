import { describe, expect, it } from "vitest";

import {
  MAX_BASE64_CHARS,
  MAX_FILE_BYTES,
  base64Length,
  fileSizeProblem,
  fileToBase64,
  parseMarkers,
} from "./upload";

describe("upload helpers", () => {
  it("agrees with the server's base64 limit", () => {
    expect(base64Length(MAX_FILE_BYTES)).toBe(MAX_BASE64_CHARS);
    expect(base64Length(3)).toBe(4);
    expect(base64Length(4)).toBe(8);
  });

  it("encodes exact bytes, including non-UTF-8 ones", async () => {
    const bytes = new Uint8Array([0x61, 0x2c, 0x62, 0x0a, 0xff, 0x00]);
    const encoded = await fileToBase64(new Blob([bytes]));
    expect(encoded).toBe("YSxiCv8A");
    expect(Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0))).toEqual(bytes);
  });

  it("encodes files larger than one chunk", async () => {
    const bytes = new Uint8Array(100_000).map((_, i) => i % 251);
    const encoded = await fileToBase64(new Blob([bytes]));
    expect(encoded.length).toBe(base64Length(bytes.length));
    expect(Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0))).toEqual(bytes);
  });

  it("refuses files over the limit before upload", () => {
    expect(fileSizeProblem(MAX_FILE_BYTES)).toBeNull();
    expect(fileSizeProblem(MAX_FILE_BYTES + 1)).toMatch(/limit is 2 MiB/);
  });

  it("parses markers", () => {
    expect(parseMarkers(" NA, N/A ,, null ")).toEqual(["NA", "N/A", "null"]);
    expect(parseMarkers("")).toEqual([]);
  });
});
