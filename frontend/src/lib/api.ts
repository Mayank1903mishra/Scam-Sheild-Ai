export type InputKind = "paste" | "url" | "screenshot";
export type RiskBand = "high" | "medium" | "low" | "uncertain";

/** Backend origin used when VITE_API_BASE is not set. Without this the UI
 * would silently run on demo data and never reach the FastAPI service. */
export const DEFAULT_API_BASE = "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = "UNKNOWN_ERROR", status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function apiBase(): string {
  const configured = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "");
  return configured || DEFAULT_API_BASE;
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = "UNKNOWN_ERROR";
  let message = `Request failed (status ${response.status})`;
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    code = body?.error?.code || code;
    message = body?.error?.message || message;
  } catch {
    // Non-JSON error body: keep the generic message.
  }
  return new ApiError(message, code, response.status);
}

export interface AnalyzeInput {
  kind: InputKind;
  content?: string;
  file?: File;
}

export interface EvidenceItem {
  id: string;
  source: "text" | "url" | "ocr" | "intel";
  title: string;
  reason: string;
  snippet: string;
  weight: number;
  tone: "danger" | "warning" | "positive";
}

export interface ScanResult {
  id: string;
  createdAt: string;
  inputType: InputKind;
  score: number;
  band: RiskBand;
  category: string;
  uncertainty: "low" | "medium" | "high";
  uncertaintyReasons: string[];
  verdict: string;
  summary: string;
  /** "live" = produced by the FastAPI backend; "demo" = local placeholder. */
  mode: "live" | "demo";
  disclaimer: string;
  scoreNote: string;
  modules: Array<{ name: string; score: number; label: string; color: "coral" | "amber" | "violet" | "mint" }>;
  evidence: EvidenceItem[];
  entities: string[];
  ocrText?: string;
  recommendations: string[];
  intel: { label: string; detail: string; status: "on" | "off" };
}

export interface HistoryItem extends Pick<ScanResult, "id" | "createdAt" | "score" | "band" | "category" | "inputType" | "summary"> {}

interface BackendScanResponse {
  id: string;
  created_at: string;
  input_types: Array<"text" | "url" | "image">;
  risk_score: number;
  risk_band: "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH" | "UNCERTAIN";
  score_note: string;
  category: string | null;
  uncertainty: { level: "low" | "medium" | "high"; reasons: string[] };
  modules: { text: number; url: number; ocr_confidence: number | null };
  evidence: Array<{ id: string; source: "text" | "url" | "ocr" | "intel"; reason: string; snippet: string; weight: number }>;
  extracted: { urls: string[]; emails: string[]; phones: string[]; domains: string[] };
  recommendations: string[];
  disclaimer: string;
  mode: "rules" | "ml" | "demo";
  /** External source checks; returned on scan creation only. */
  sources?: Array<{ source: string; status: string; checked_at: string; detail: string; evidence_count: number }>;
  ocr_text: string | null;
}

interface BackendScanListItem {
  id: string;
  created_at: string;
  input_types: Array<"text" | "url" | "image">;
  risk_score: number;
  risk_band: "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH" | "UNCERTAIN";
  category: string | null;
}

const historyStorageKey = "scamshield-demo-history";

function mapBand(backendBand: BackendScanResponse["risk_band"]): RiskBand {
  switch (backendBand) {
    case "HIGH":
    case "VERY_HIGH":
      return "high";
    case "MODERATE":
      return "medium";
    case "LOW":
      return "low";
    case "UNCERTAIN":
      return "uncertain";
  }
}

function mapInputType(types: BackendScanResponse["input_types"]): InputKind {
  if (types.includes("image")) return "screenshot";
  if (types.includes("url")) return "url";
  return "paste";
}

function mapModuleScores(modules: BackendScanResponse["modules"]): ScanResult["modules"] {
  const result: ScanResult["modules"] = [
    { name: "Message signals", score: modules.text, label: modules.text > 50 ? "Strong pressure language" : modules.text > 20 ? "Some urgency detected" : "No urgency language", color: "coral" },
    { name: "Link structure", score: modules.url, label: modules.url > 50 ? "Suspicious URL structure" : modules.url > 20 ? "Minor URL anomalies" : "No suspicious link", color: "amber" },
    { name: "Context match", score: Math.max(modules.text, modules.url), label: "Known scam pattern", color: "violet" },
    { name: "Safety checks", score: modules.ocr_confidence !== null ? Math.round(modules.ocr_confidence * 100) : 0, label: modules.ocr_confidence !== null ? "OCR confidence" : "Low-risk context", color: "mint" },
  ];
  return result;
}

function mapEvidence(evidence: BackendScanResponse["evidence"]): EvidenceItem[] {
  return evidence.map((item) => {
    let tone: EvidenceItem["tone"] = "warning";
    if (item.weight > 0) tone = "danger";
    else if (item.weight < 0) tone = "positive";
    return {
      id: item.id,
      source: item.source,
      title: item.reason,
      reason: item.reason,
      snippet: item.snippet,
      weight: Math.abs(item.weight),
      tone,
    };
  });
}

function mapEntities(extracted: BackendScanResponse["extracted"]): string[] {
  const entities: string[] = [];
  entities.push(...extracted.urls);
  entities.push(...extracted.emails);
  entities.push(...extracted.phones);
  entities.push(...extracted.domains);
  return [...new Set(entities)];
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  
  if (diffHours < 1) {
    const mins = Math.floor(diffMs / (1000 * 60));
    return `Today · ${mins}m ago`;
  } else if (diffHours < 24) {
    return `Today · ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  } else if (diffDays < 2) {
    return `Yesterday · ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  } else if (diffDays < 7) {
    return `${date.toLocaleDateString([], { weekday: 'short' })} · ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  } else {
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  }
}

function getVerdict(band: RiskBand, category: string): string {
  switch (band) {
    case "high":
      return "High risk — do not click or reply.";
    case "medium":
      return "Pause here — verify before you act.";
    case "low":
      return "No strong scam signals found.";
    case "uncertain":
      return "Not enough information to assess confidently.";
  }
}

function mapIntel(sources: BackendScanResponse["sources"]): ScanResult["intel"] {
  const label = "External lookups";
  if (!sources || sources.length === 0) {
    return {
      label,
      detail: "Source checks are not stored with history, so this read cannot show them. Raw content is never kept.",
      status: "off",
    };
  }
  const summary = sources.map((check) => `${check.source}: ${check.status}`).join(" · ");
  const active = sources.some((check) => check.status !== "disabled");
  return {
    label,
    detail: active
      ? `Public sources only — ${summary}. Your raw content stays local.`
      : `No outbound lookups were made — ${summary}.`,
    status: active ? "on" : "off",
  };
}

function convertBackendResponse(backend: BackendScanResponse): ScanResult {
  const band = mapBand(backend.risk_band);
  const inputType = mapInputType(backend.input_types);
  const createdAt = formatDate(backend.created_at);
  const category = backend.category || "No strong indicators";
  const uncertainty = backend.uncertainty.level;
  const verdict = getVerdict(band, category);
  const summary = backend.evidence.length > 0
    ? `Found ${backend.evidence.length} signal(s) totaling ${backend.risk_score} points — ${category.toLowerCase()}.`
    : "No risk indicators detected in your input.";
  
  return {
    id: backend.id,
    createdAt,
    inputType,
    score: backend.risk_score,
    band,
    category,
    uncertainty,
    uncertaintyReasons: backend.uncertainty.reasons ?? [],
    verdict,
    summary,
    mode: backend.mode === "demo" ? "demo" : "live",
    disclaimer: backend.disclaimer,
    scoreNote: backend.score_note,
    modules: mapModuleScores(backend.modules),
    evidence: mapEvidence(backend.evidence),
    entities: mapEntities(backend.extracted),
    ocrText: backend.ocr_text || undefined,
    recommendations: backend.recommendations.length > 0 ? backend.recommendations : [
      "Stay cautious with any requests for personal information or payment.",
      "Verify the sender through official channels if unsure."
    ],
    intel: mapIntel(backend.sources),
  };
}

function convertBackendListItem(backend: BackendScanListItem): HistoryItem {
  const band = mapBand(backend.risk_band);
  const inputType = mapInputType(backend.input_types);
  const createdAt = formatDate(backend.created_at);
  const category = backend.category || "No strong indicators";
  
  return {
    id: backend.id,
    createdAt,
    score: backend.risk_score,
    band,
    category,
    inputType,
    summary: `Scanned as ${band} risk (${backend.risk_score}/100) — ${category.toLowerCase()}.`,
  };
}

function saveDemoHistory(result: ScanResult): void {
  if (typeof localStorage === "undefined") return;
  try {
    const current = JSON.parse(localStorage.getItem(historyStorageKey) ?? "[]") as HistoryItem[];
    const item: HistoryItem = { id: result.id, createdAt: result.createdAt, score: result.score, band: result.band, category: result.category, inputType: result.inputType, summary: result.summary };
    localStorage.setItem(historyStorageKey, JSON.stringify([item, ...current.filter((entry) => entry.id !== item.id)].slice(0, 30)));
  } catch {
    // Demo persistence is best-effort only.
  }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function analyzeScan(input: AnalyzeInput): Promise<ScanResult> {
  const baseUrl = apiBase();
  let clientError: ApiError | undefined;
  try {
    const isScreenshot = input.kind === "screenshot";
    const body = isScreenshot ? (() => {
      const form = new FormData();
      if (input.file) form.append("file", input.file);
      if (input.content) form.append("text", input.content);
      return form;
    })() : JSON.stringify({ text: input.kind === "paste" ? input.content : undefined, url: input.kind === "url" ? input.content : undefined });
    const response = await fetch(`${baseUrl}/api/v1/scans${isScreenshot ? "/upload" : ""}`, {
      method: "POST",
      headers: isScreenshot ? undefined : { "Content-Type": "application/json" },
      body,
    });
    if (response.ok) {
      const backendResult = (await response.json()) as BackendScanResponse;
      const result = convertBackendResponse(backendResult);
      saveDemoHistory(result);
      return result;
    }
    const error = await toApiError(response);
    // 4xx means the request itself was rejected (validation, rate limit).
    // Surface that instead of quietly returning fabricated results.
    if (error.status >= 400 && error.status < 500) clientError = error;
  } catch {
    // Network failure or 5xx: fail open to demo data below.
  }
  if (clientError) throw clientError;
  await wait(850);
  const result = getMockResult(input.kind);
  saveDemoHistory(result);
  return result;
}

export async function getScan(id: string): Promise<ScanResult> {
  const response = await fetch(`${apiBase()}/api/v1/scans/${id}`);
  if (!response.ok) throw await toApiError(response);
  return convertBackendResponse((await response.json()) as BackendScanResponse);
}

export async function listScans(): Promise<HistoryItem[]> {
  try {
    const response = await fetch(`${apiBase()}/api/v1/scans`);
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data)) {
        return data.map(convertBackendListItem);
      }
    }
  } catch {
    // Fall through to the local demo history.
  }
  await wait(180);
  if (typeof localStorage !== "undefined") {
    try {
      const stored = JSON.parse(localStorage.getItem(historyStorageKey) ?? "[]") as HistoryItem[];
      if (stored.length) return stored;
    } catch {
      // Fall through to seed history.
    }
  }
  return mockHistory;
}

/** Returns false only when the server explicitly rejected the delete. */
export async function deleteScan(id: string): Promise<boolean> {
  try {
    const response = await fetch(`${apiBase()}/api/v1/scans/${id}`, { method: "DELETE" });
    if (!response.ok) return false;
    return true;
  } catch {
    // API unreachable: fall back to local-only cleanup below.
  }
  if (typeof localStorage !== "undefined") {
    try {
      const current = JSON.parse(localStorage.getItem(historyStorageKey) ?? "[]") as HistoryItem[];
      localStorage.setItem(historyStorageKey, JSON.stringify(current.filter((item) => item.id !== id)));
    } catch {
      // Demo persistence is best-effort only.
    }
  }
  return true;
}

/** Returns true when the server accepted the feedback. */
export async function sendFeedback(id: string, helpful: boolean): Promise<boolean> {
  try {
    const response = await fetch(`${apiBase()}/api/v1/scans/${id}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ helpful }),
    });
    return response.ok;
  } catch {
    // Feedback is non-blocking and should never interrupt the result view.
    return false;
  }
}

const mockResult: ScanResult = {
  id: "scan_9f18d",
  createdAt: "Just now",
  inputType: "paste",
  score: 78,
  band: "high",
  category: "Credential harvesting",
  uncertainty: "low",
  uncertaintyReasons: ["Demo result — no live analysis was run."],
  verdict: "High risk — do not click or reply.",
  summary: "This message stacks urgency, a fake account warning, and a direct request for your login code.",
  mode: "demo",
  disclaimer: "Demo placeholder. Risk indicators are not proof of fraud — always verify independently.",
  scoreNote: "Demo score, not a real analysis.",
  modules: [
    { name: "Message signals", score: 86, label: "Pressure language", color: "coral" },
    { name: "Link structure", score: 72, label: "Lookalike domain", color: "amber" },
    { name: "Context match", score: 64, label: "Known scam pattern", color: "violet" },
    { name: "Safety checks", score: 18, label: "No confirmed listing", color: "mint" },
  ],
  evidence: [
    { id: "e1", source: "text", title: "Urgency + countdown", reason: "The message says access will be removed today unless you act immediately.", snippet: "…verify your account within 15 minutes…", weight: 24, tone: "danger" },
    { id: "e2", source: "text", title: "Credential request", reason: "Legitimate support teams never ask for a one-time password in chat.", snippet: "…send the 6-digit code to keep your account active…", weight: 31, tone: "danger" },
    { id: "e3", source: "url", title: "Brand lookalike", reason: "The link imitates a familiar brand but uses a newly registered, unusual domain.", snippet: "secure-account-check[.]info/login", weight: 18, tone: "warning" },
    { id: "e4", source: "text", title: "Payment pressure", reason: "The sender introduces a fee to make the request feel official and harder to ignore.", snippet: "…small reactivation fee applies…", weight: 12, tone: "warning" },
  ],
  entities: ["secure-account-check.info", "6-digit OTP", "account access", "reactivation fee"],
  recommendations: [
    "Do not open the link or share any code, password, or payment details.",
    "Open the official app yourself and check notifications there instead.",
    "Report the message to the platform, then block the sender.",
  ],
  intel: { label: "External lookups", detail: "Optional checks are off — your content stays local.", status: "off" },
};

const mockHistory: HistoryItem[] = [
  { id: "scan_9f18d", createdAt: "Today · 2:14 PM", score: 78, band: "high", category: "Credential harvesting", inputType: "paste", summary: "Urgent account warning asking for a one-time code." },
  { id: "scan_71be2", createdAt: "Yesterday · 6:42 PM", score: 41, band: "medium", category: "Suspicious promotion", inputType: "url", summary: "Giveaway page with a shortened link and payment prompt." },
  { id: "scan_2ab90", createdAt: "Oct 06 · 11:09 AM", score: 9, band: "low", category: "No strong indicators", inputType: "screenshot", summary: "Club event poster with a verified campus contact." },
];

export function getMockResult(kind: InputKind, id = `scan_${Math.random().toString(16).slice(2, 8)}`): ScanResult {
  if (kind === "url") {
    return {
      ...mockResult,
      id,
      inputType: "url",
      score: 56,
      band: "medium",
      category: "Suspicious promotion",
      uncertainty: "medium",
      verdict: "Pause here — verify before you act.",
      summary: "This URL has a shortened path and a payment prompt, but there is not enough evidence to call it confirmed fraud.",
      modules: [
        { name: "Message signals", score: 42, label: "Prize language", color: "coral" },
        { name: "Link structure", score: 74, label: "Shortened URL", color: "amber" },
        { name: "Context match", score: 48, label: "Promo pattern", color: "violet" },
        { name: "Safety checks", score: 24, label: "No confirmed listing", color: "mint" },
      ],
      evidence: [
        { id: "u1", source: "url", title: "Shortener hides destination", reason: "Short links make it harder to preview where you will land before opening.", snippet: "short.ly/3x9a → destination hidden", weight: 22, tone: "warning" },
        { id: "u2", source: "url", title: "Payment pressure", reason: "A giveaway that asks for a processing fee is a common scam pattern.", snippet: "…pay ₹49 to release your prize…", weight: 21, tone: "danger" },
        { id: "u3", source: "url", title: "No confirmed threat match", reason: "No optional external threat-list match was returned for this scan.", snippet: "safe browsing lookup: no match", weight: 0, tone: "positive" },
      ],
      entities: ["short.ly/3x9a", "₹49 processing fee", "giveaway prize"],
      recommendations: ["Do not pay a fee to claim a surprise prize.", "Preview the destination with a URL expander or search the official brand yourself.", "If you already entered details, change the password and contact your bank."],
    };
  }
  if (kind === "screenshot") {
    return {
      ...mockResult,
      id,
      inputType: "screenshot",
      score: 18,
      band: "low",
      category: "No strong indicators",
      uncertainty: "medium",
      verdict: "No strong scam signals found.",
      summary: "OCR found a normal campus event notice with no pressure language or credential request.",
      modules: [
        { name: "Message signals", score: 8, label: "No urgency language", color: "coral" },
        { name: "Link structure", score: 12, label: "No suspicious link", color: "amber" },
        { name: "Context match", score: 20, label: "Campus event pattern", color: "violet" },
        { name: "Safety checks", score: 88, label: "Low-risk context", color: "mint" },
      ],
      evidence: [
        { id: "o1", source: "ocr", title: "No credential request", reason: "The extracted text does not ask for a password, OTP, or account recovery code.", snippet: "no login or verification language found", weight: 0, tone: "positive" },
        { id: "o2", source: "ocr", title: "Campus context", reason: "The poster uses a campus contact and a normal event time without urgency pressure.", snippet: "Friday 4 PM · club@campus.example", weight: 0, tone: "positive" },
      ],
      entities: ["campus.example", "club@campus.example", "Friday 4 PM"],
      ocrText: "Campus coding club meetup · Friday 4 PM · Room B204 · contact club@campus.example",
      recommendations: ["Check the club's official campus page if you want an extra confirmation.", "Avoid sharing personal details just to RSVP to an event.", "If the poster is being forwarded, keep the original source visible."],
    };
  }
  return { ...mockResult, id, inputType: "paste" };
}