import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  DEFAULT_API_BASE,
  analyzeScan,
  deleteScan,
  getScan,
  listScans,
  sendFeedback,
} from "./api";

const backendScan = {
  id: "11111111-2222-3333-4444-555555555555",
  created_at: "2026-10-10T21:17:23",
  input_types: ["text"],
  risk_score: 45,
  risk_band: "MODERATE",
  score_note: "Heuristic score, not a probability; thresholds provisional.",
  category: "PHISHING",
  uncertainty: { level: "medium", reasons: ["Conflicting signals from different analysis modules"] },
  modules: { text: 30, url: 0, ocr_confidence: 0 },
  evidence: [
    {
      id: "CREDENTIAL_REQUEST",
      source: "text",
      reason: "Asks for a password or OTP.",
      snippet: "send the 6-digit code",
      weight: 30,
    },
  ],
  extracted: { urls: [], emails: [], phones: [], domains: [] },
  recommendations: ["Verify the sender through official channels if unsure."],
  disclaimer: "Risk indicators are not proof of fraud.",
  mode: "rules",
  sources: [
    { source: "i4c", status: "disabled", checked_at: "now", detail: "disabled", evidence_count: 0 },
    { source: "safebrowsing", status: "checked", checked_at: "now", detail: "checked", evidence_count: 0 },
  ],
  ocr_text: null,
};

const listItem = {
  id: backendScan.id,
  created_at: backendScan.created_at,
  input_types: ["text"],
  risk_score: 45,
  risk_band: "MODERATE",
  category: "PHISHING",
};

function fakeResponse(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("API base", () => {
  it("defaults to the local FastAPI service", () => {
    expect(DEFAULT_API_BASE).toBe("http://localhost:8000");
  });

  it("honours VITE_API_BASE when it is set", async () => {
    vi.stubEnv("VITE_API_BASE", "http://localhost:9000/");
    const fetchMock = vi.fn().mockResolvedValue(fakeResponse([listItem]));
    vi.stubGlobal("fetch", fetchMock);

    await listScans();

    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:9000/api/v1/scans");
  });
});

describe("analyzeScan", () => {
  it("posts to the backend and maps the response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(fakeResponse(backendScan));
    vi.stubGlobal("fetch", fetchMock);

    const result = await analyzeScan({ kind: "paste", content: "send the code now" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${DEFAULT_API_BASE}/api/v1/scans`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ text: "send the code now", url: undefined });

    expect(result.mode).toBe("live");
    expect(result.band).toBe("medium");
    expect(result.score).toBe(45);
    expect(result.disclaimer).toBe("Risk indicators are not proof of fraud.");
    expect(result.scoreNote).toContain("not a probability");
    expect(result.uncertaintyReasons).toEqual([
      "Conflicting signals from different analysis modules",
    ]);
    expect(result.evidence[0].source).toBe("text");
  });

  it("reports external source checks", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse(backendScan)));

    const result = await analyzeScan({ kind: "paste", content: "anything at all" });

    expect(result.intel.status).toBe("on");
    expect(result.intel.detail).toContain("i4c: disabled");
    expect(result.intel.detail).toContain("Your raw content stays local.");
  });

  it("surfaces 4xx errors instead of inventing a result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        fakeResponse(
          { error: { code: "RATE_LIMITED", message: "Too many requests (limit: 30 per 1 minute)." } },
          429,
        ),
      ),
    );

    await expect(analyzeScan({ kind: "paste", content: "hello there" })).rejects.toMatchObject({
      name: "ApiError",
      code: "RATE_LIMITED",
      status: 429,
      message: "Too many requests (limit: 30 per 1 minute).",
    });
  });

  it("falls back to a clearly labelled demo result when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));

    const result = await analyzeScan({ kind: "paste", content: "hello there" });

    expect(result.mode).toBe("demo");
    expect(result.disclaimer).toContain("Demo placeholder");
  });

  it("posts a multipart body for screenshots", async () => {
    const fetchMock = vi.fn().mockResolvedValue(fakeResponse({ ...backendScan, input_types: ["image"], ocr_text: "SEND OTP" }));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["binary"], "shot.png", { type: "image/png" });
    const result = await analyzeScan({ kind: "screenshot", file });

    expect(fetchMock.mock.calls[0][0]).toBe(`${DEFAULT_API_BASE}/api/v1/scans/upload`);
    expect(fetchMock.mock.calls[0][1].body).toBeInstanceOf(FormData);
    expect(result.inputType).toBe("screenshot");
    expect(result.ocrText).toBe("SEND OTP");
  });
});

describe("getScan", () => {
  it("returns the stored scan", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse(backendScan)));

    const result = await getScan(backendScan.id);

    expect(result.id).toBe(backendScan.id);
    expect(result.mode).toBe("live");
    expect(result.score).toBe(45);
  });

  it("throws a typed error when the scan is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(fakeResponse({ error: { code: "HTTP_ERROR", message: "Scan not found" } }, 404)),
    );

    await expect(getScan("nope")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("listScans", () => {
  it("maps backend history items", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse([listItem])));

    const items = await listScans();

    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ id: backendScan.id, band: "medium", score: 45 });
  });
});

describe("deleteScan", () => {
  it("reports success on 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse(null, 204)));

    await expect(deleteScan(backendScan.id)).resolves.toBe(true);
  });

  it("reports failure when the server rejects the delete", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(fakeResponse({ error: { code: "HTTP_ERROR", message: "Scan not found" } }, 404)),
    );

    await expect(deleteScan("missing")).resolves.toBe(false);
  });

  it("cleans up locally when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(deleteScan("scan_local")).resolves.toBe(true);
  });
});

describe("sendFeedback", () => {
  it("returns true when the server accepts it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse({ message: "Feedback submitted" })));

    await expect(sendFeedback(backendScan.id, true)).resolves.toBe(true);
  });

  it("returns false when the scan does not exist", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(fakeResponse({ error: { code: "HTTP_ERROR", message: "Scan not found" } }, 404)),
    );

    await expect(sendFeedback("missing", true)).resolves.toBe(false);
  });

  it("returns false instead of rejecting when offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(sendFeedback(backendScan.id, false)).resolves.toBe(false);
  });
});
