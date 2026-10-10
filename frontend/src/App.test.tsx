import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const DISCLAIMER =
  "Risk indicators are not proof of fraud. Legitimate opportunities may be flagged (false positive).";

const backendScan = {
  id: "11111111-2222-3333-4444-555555555555",
  created_at: "2026-10-10T21:17:23",
  input_types: ["text"],
  risk_score: 45,
  risk_band: "MODERATE",
  score_note: "Heuristic score, not a probability; thresholds provisional.",
  category: "PHISHING",
  uncertainty: {
    level: "medium",
    reasons: ["Conflicting signals from different analysis modules"],
  },
  modules: { text: 30, url: 0, ocr_confidence: 0 },
  evidence: [
    {
      id: "CREDENTIAL_REQUEST",
      source: "text",
      reason: "Asks for a password or OTP.",
      snippet: '<img src="x" onerror="window.__pwned = 1"> send the 6-digit code',
      weight: 30,
    },
  ],
  extracted: { urls: [], emails: [], phones: [], domains: [] },
  recommendations: ["Verify the sender through official channels if unsure."],
  disclaimer: DISCLAIMER,
  mode: "rules",
  sources: [
    { source: "i4c", status: "disabled", checked_at: "now", detail: "disabled", evidence_count: 0 },
    { source: "safebrowsing", status: "disabled", checked_at: "now", detail: "disabled", evidence_count: 0 },
  ],
  ocr_text: null,
};

const historyItem = {
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

function stubMatchMedia() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

async function submitText(value: string) {
  fireEvent.change(screen.getByLabelText("Text to scan"), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: /scan for signals/i }));
}

beforeEach(() => {
  window.history.replaceState({}, "", "/");
  stubMatchMedia();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("scan flow", () => {
  it("sends the text to the backend and renders the real explanation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(fakeResponse(backendScan));
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<App />);
    await submitText("please send the otp now to confirm your account");

    expect(await screen.findByText(DISCLAIMER)).toBeTruthy();
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/scans");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      text: "please send the otp now to confirm your account",
    });

    // Safety text that used to be dropped now reaches the UI.
    expect(screen.getByText(/not a probability/)).toBeTruthy();
    expect(
      screen.getByText("Conflicting signals from different analysis modules"),
    ).toBeTruthy();
    // A live analysis is not labelled as demo data.
    expect(screen.queryByText(/DEMO DATA/i)).toBeNull();
    // Evidence snippets render as text, never as markup.
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/onerror/)).toBeTruthy();
  });

  it("labels the result as demo data when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));

    render(<App />);
    await submitText("hello there friend");

    expect(await screen.findByText(/DEMO DATA/i, {}, { timeout: 4000 })).toBeTruthy();
  });

  it("shows the backend error instead of a fabricated result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        fakeResponse(
          { error: { code: "RATE_LIMITED", message: "Too many requests (limit: 30 per 1 minute)." } },
          429,
        ),
      ),
    );

    const { container } = render(<App />);
    await submitText("hello there friend");

    expect(await screen.findByText(/Too many requests/)).toBeTruthy();
    expect(container.querySelector(".result-layout")).toBeNull();
  });

  it("posts feedback for a live result", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) =>
      url.endsWith("/feedback") ? fakeResponse({ message: "Feedback submitted" }) : fakeResponse(backendScan),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await submitText("please send the otp now to confirm your account");
    await screen.findByText(DISCLAIMER);

    fireEvent.click(screen.getByRole("button", { name: /yep/i }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).endsWith("/feedback")),
      ).toBe(true),
    );
  });
});

describe("history flow", () => {
  it("loads a stored scan from the backend instead of showing demo evidence", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (String(url).endsWith("/api/v1/scans")) return fakeResponse([historyItem]);
      return fakeResponse(backendScan);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /see your recent scans/i }));

    expect(await screen.findByText(/Scanned as medium risk/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /open result/i }));

    expect(await screen.findByText(DISCLAIMER)).toBeTruthy();
    expect(screen.queryByText(/DEMO DATA/i)).toBeNull();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes(`/scans/${backendScan.id}`)),
    ).toBe(true);
  });
});
