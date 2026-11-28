import { useEffect, useState, type ChangeEvent } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Ban,
  BarChart3,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Copy,
  FileImage,
  FileSearch2,
  Fingerprint,
  Flag,
  History,
  Inbox,
  Info,
  LaptopMinimalCheck,
  Link2,
  LockKeyhole,
  MessageCircleWarning,
  MousePointer2,
  Network,
  RotateCcw,
  ScanLine,
  Search,
  Shield,
  ShieldAlert,
  Sparkles,
  Sun,
  Moon,
  Globe,
  Trash2,
  UploadCloud,
  WandSparkles,
  Zap,
  Phone,
import { analyzeScan, deleteScan, getMockResult, getScan, listScans, sendFeedback, type HistoryItem, type InputKind, type ScanResult, type Signal } from "./lib/api";

type View = "scan" | "result" | "history";

const inputTabs: Array<{ id: InputKind; label: string; icon: typeof MessageCircleWarning }> = [
  { id: "paste", label: "Paste text", icon: MessageCircleWarning },
  { id: "url", label: "Check a URL", icon: Link2 },
  { id: "screenshot", label: "Upload screenshot", icon: FileImage },
];

function getInitialView(): View {
  return window.location.pathname === "/history" ? "history" : "scan";
}

function isValidUrl(value: string) {
  try {
    const url = new URL(value.trim());
    return (url.protocol === "http:" || url.protocol === "https:") && Boolean(url.hostname);
  } catch {
    return false;
  }
}

const SCAN_STAGES = [
  "Uploading input...",
  "Extracting text and signals...",
  "Checking suspicious patterns...",
  "Evaluating risk indicators...",
  "Preparing security report...",
];

function App() {
  const [view, setView] = useState<View>(getInitialView);
  const [inputKind, setInputKind] = useState<InputKind>("paste");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | undefined>();
  const [filePreview, setFilePreview] = useState<string | undefined>();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [scanningStage, setScanningStage] = useState(0);
  const [result, setResult] = useState<ScanResult | undefined>();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [toast, setToast] = useState<string | undefined>();
  const [lang, setLang] = useState<"en" | "hi">(() => {
    const stored = localStorage.getItem("scamshield-lang");
    return stored === "hi" ? "hi" : "en";
  });
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const stored = localStorage.getItem("scamshield-theme");
    return stored === "light" ? "light" : "dark";
  });

  const TR: Record<string, Record<"en" | "hi", string>> = {
    "nav.scan": { en: "Scan", hi: "स्कैन" },
    "nav.history": { en: "History", hi: "इतिहास" },
    "btn.new-scan": { en: "New scan", hi: "नया स्कैन" },
    "btn.open-result": { en: "Open result", hi: "परिणाम खोलें" },
    "btn.delete": { en: "Delete", hi: "हटाएं" },
    "lang.switch": { en: "English", hi: "हिन्दी" },
    "theme.toggle": { en: "Light mode", hi: "लाइट मोड" },
    "verdict.select": { en: "SELECT", hi: "चुनें" },
    "verdict.reject": { en: "REJECT", hi: "अस्वीकार करें" },
    "verdict.verify": { en: "VERIFY BEFORE SELECTING", hi: "चुनने से पहले सत्यापित करें" },
    "section.select": { en: "Reasons to SELECT", hi: "चुनने के कारण" },
    "section.reject": { en: "Reasons to REJECT", hi: "अस्वीकार करने के कारण" },
    "label.evidence": { en: "Evidence", hi: "सबूत" },
    "label.severity": { en: "Severity", hi: "गंभीरता" },
    "sev.high": { en: "High", hi: "उच्च" },
    "sev.medium": { en: "Medium", hi: "मध्यम" },
    "sev.low": { en: "Low", hi: "कम" },
    "label.confidence": { en: "Confidence", hi: "विश्वास स्तर" },
    "label.risk-level": { en: "Risk level", hi: "जोखिम स्तर" },
    "label.score": { en: "Risk score", hi: "जोखिम स्कोर" },
    "msg.insufficient": { en: "Evidence is insufficient — verify before acting.", hi: "सबूत अपर्याप्त है — कार्रवाई से पहले सत्यापित करें." },
    "msg.no-signals": { en: "No clear signals detected.", hi: "कोई स्पष्ट संकेत नहीं मिला." },
    "footer.tag": { en: "is a signal scanner, not a crystal ball.", hi: "एक सिग्नल स्कैनर है, कोई क्रिस्टल बॉल नहीं।" },
  };

  function t(key: string): string {
    return TR[key]?.[lang] || key;
  }

  useEffect(() => {
    localStorage.setItem("scamshield-lang", lang);
  }, [lang]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.classList.toggle("light", theme === "light");
    localStorage.setItem("scamshield-theme", theme);
  }, [theme]);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const moveCursor = (event: MouseEvent) => {
      document.documentElement.style.setProperty("--cursor-x", `${event.clientX}px`);
      document.documentElement.style.setProperty("--cursor-y", `${event.clientY}px`);
    };
    window.addEventListener("mousemove", moveCursor, { passive: true });
    return () => window.removeEventListener("mousemove", moveCursor);
  }, []);

  useEffect(() => {
    const onPopState = () => setView(window.location.pathname === "/history" ? "history" : "scan");
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!isAnalyzing) { setScanningStage(0); return; }
    const timer = setInterval(() => setScanningStage((s) => (s + 1) % SCAN_STAGES.length), 900);
    return () => clearInterval(timer);
  }, [isAnalyzing]);

  useEffect(() => {
    if (view !== "history") return;
    listScans().then((items) => {
      setHistory(items);
      setHistoryLoaded(true);
    });
  }, [view]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(undefined), 2800);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => () => {
    if (filePreview) URL.revokeObjectURL(filePreview);
  }, [filePreview]);

  const analyze = async () => {
    if (inputKind !== "screenshot" && content.trim().length < 5) {
      setToast("Add a little more context so the scanner can find meaningful signals.");
      return;
    }
    if (inputKind === "url" && !isValidUrl(content)) {
      setToast("That doesn't look like a full http(s) URL yet.");
      return;
    }
    if (inputKind === "screenshot" && !file) {
      setToast("Choose a PNG, JPG, or WebP screenshot first.");
      return;
    }
    setIsAnalyzing(true);
    try {
      const next = await analyzeScan({ kind: inputKind, content, file });
      setResult(next);
      setHistory((prev) => {
        const item: HistoryItem = {
          id: next.id,
          createdAt: next.createdAt,
          score: next.score,
          band: next.band,
          category: next.category,
          inputType: next.inputType,
          summary: next.summary,
        };
        const exists = prev.some((p) => p.id === next.id);
        return exists ? prev.map((p) => (p.id === next.id ? item : p)) : [item, ...prev];
      });
      setHistoryLoaded(false);
      setView("result");
    } catch (error) {
      const message = error instanceof Error ? error.message : "The scan could not be completed. Please try again.";
      setToast(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const resetScan = () => {
    window.history.pushState({}, "", "/scan");
    setView("scan");
    setContent("");
    setFile(undefined);
    setFilePreview(undefined);
  };

  const selectTab = (kind: InputKind) => {
    setInputKind(kind);
    setContent("");
    setFile(undefined);
    setFilePreview(undefined);
  };

  const acceptFile = (next?: File) => {
    if (!next) return;
    if (!/^image\/(png|jpeg|webp)$/.test(next.type) || next.size > 5 * 1024 * 1024) {
      setToast("Use a PNG, JPG, or WebP under 5 MB.");
      return;
    }
    setFile(next);
    setFilePreview(URL.createObjectURL(next));
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => acceptFile(event.target.files?.[0]);

  const openHistoryItem = async (item: HistoryItem) => {
    if (result?.id === item.id) {
      setView("result");
      return;
    }
    window.history.pushState({}, "", "/scan");
    try {
      setResult(await getScan(item.id));
    } catch {
      setToast("Couldn't load that scan from the server — showing a demo preview.");
      setResult({ ...getMockResult(item.inputType, item.id), id: item.id, createdAt: item.createdAt, score: item.score, band: item.band, category: item.category, summary: item.summary, verdict: item.band === "high" ? "High risk — do not click or reply." : item.band === "medium" ? "Pause here — verify before you act." : "No strong scam signals found." });
    }
    setView("result");
  };

  const deleteHistoryItem = async (id: string) => {
    const removed = await deleteScan(id);
    if (!removed) {
      setToast("The server refused that delete — the scan is still in your history.");
      return;
    }
    setHistory((items) => items.filter((item) => item.id !== id));
    if (result?.id === id) setResult(undefined);
    setToast("Scan removed from your history.");
  };

  return (
    <div className="app-shell">
      <div className="cursor-orb" aria-hidden="true" />
      <div className="noise" aria-hidden="true" />
      <Header view={view} onNavigate={(next) => next === "scan" ? resetScan() : (window.history.pushState({}, "", "/history"), setView(next))} lang={lang} theme={theme} setLang={setLang} setTheme={setTheme} t={t} />
      <main className="main-stage">
        {view === "scan" && <ScanView inputKind={inputKind} content={content} filePreview={filePreview} fileName={file?.name} isAnalyzing={isAnalyzing} onTab={selectTab} onContentChange={setContent} onFileChange={onFileChange} onFileDrop={acceptFile} onAnalyze={analyze} onHistory={() => { window.history.pushState({}, "", "/history"); setView("history"); }} />}
        {view === "result" && result && <ResultView result={result} onBack={() => setView("scan")} onNewScan={resetScan} onToast={setToast} lang={lang} t={t} />}
        {view === "history" && <HistoryView items={history} loaded={historyLoaded} onOpen={openHistoryItem} onDelete={deleteHistoryItem} onNewScan={resetScan} />}
        {isAnalyzing && <ScanningOverlay stage={scanningStage} filePreview={filePreview} inputKind={inputKind} />}
      </main>
      <Footer />
      {toast && <div className="toast" role="status"><Info size={16} />{toast}</div>}
    </div>
  );
}

function Header({ view, onNavigate, lang, theme, setLang, setTheme, t }: { view: View; onNavigate: (view: View) => void; lang: "en" | "hi"; theme: "dark" | "light"; setLang: (l: "en" | "hi") => void; setTheme: (t: "dark" | "light") => void; t: (key: string) => string }) {
  return (
    <header className="topbar">
      <button className="wordmark" onClick={() => onNavigate("scan")} aria-label="ScamShield home">
        <span className="mark"><Shield size={17} strokeWidth={2.8} /><span className="mark-dot" /></span>
        <span>SCAM<span className="wordmark-slash">//</span>SHIELD</span>
        <span className="wordmark-beta">AI</span>
      </button>
      <div className="topbar-center"><span className="status-pip" /> analysis engine online <span className="topbar-divider" /> privacy-aware by default</div>
      <nav className="nav-actions" aria-label="Primary navigation">
        <button className={view === "scan" || view === "result" ? "nav-link active" : "nav-link"} onClick={() => onNavigate("scan")}><ScanLine size={15} /> {t("nav.scan")}</button>
        <button className={view === "history" ? "nav-link active" : "nav-link"} onClick={() => onNavigate("history")}><History size={15} /> {t("nav.history")}</button>
      </nav>
      <div className="topbar-toggles">
        <button className="icon-button" title={t("theme.toggle")} onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={t("theme.toggle")}>{theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}</button>
        <button className="icon-button" title={t("lang.switch")} onClick={() => setLang(lang === "en" ? "hi" : "en")} aria-label={t("lang.switch")}><Globe size={15} /></button>
      </div>
    </header>
  );
}

function ScanView({ inputKind, content, filePreview, fileName, isAnalyzing, onTab, onContentChange, onFileChange, onFileDrop, onAnalyze, onHistory }: {
  inputKind: InputKind; content: string; filePreview?: string; fileName?: string; isAnalyzing: boolean; onTab: (kind: InputKind) => void; onContentChange: (value: string) => void; onFileChange: (event: ChangeEvent<HTMLInputElement>) => void; onFileDrop: (file: File) => void; onAnalyze: () => void; onHistory: () => void;
}) {
  return (
    <section className="slide-frame scan-layout">
      <div className="hero-copy">
        <div className="eyebrow"><span className="eyebrow-line" /> SCAN THE VIBE <span className="eyebrow-count">v1.4</span></div>
        <h1>Trust your <span className="headline-highlight">gut.</span><br />Then check the <span className="headline-outline">signals.</span></h1>
        <p className="hero-lede">ScamShield breaks down sketchy messages, links, and screenshots into receipts you can actually understand.</p>
        <div className="hero-meta"><div className="meta-item"><span className="meta-icon mint"><LockKeyhole size={14} /></span><span><b>privacy-aware by default</b><small>content follows your API policy</small></span></div><div className="meta-item"><span className="meta-icon violet"><Fingerprint size={14} /></span><span><b>40+ signals</b><small>every point is explainable</small></span></div></div>
        <button className="history-tease" onClick={onHistory}><Clock3 size={15} /> See your recent scans <ChevronRight size={15} /></button>
      </div>
      <div className="detector-wrap">
        <div className="detector-glow" />
        <div className="detector-card tilt-card">
          <div className="detector-topline"><span className="card-kicker"><span className="live-dot" /> READY TO CHECK</span><span className="card-id">#SS-014</span></div>
          <div className="input-tabs" role="tablist" aria-label="Scan input type">
            {inputTabs.map(({ id, label, icon: Icon }) => <button key={id} className={inputKind === id ? "input-tab active" : "input-tab"} onClick={() => onTab(id)} role="tab" aria-selected={inputKind === id}><Icon size={15} />{label}</button>)}
          </div>
          {inputKind === "screenshot" ? <UploadZone filePreview={filePreview} fileName={fileName} onFileChange={onFileChange} onFileDrop={onFileDrop} /> : <div className="textarea-shell"><textarea value={content} onChange={(event) => onContentChange(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); onAnalyze(); } }} placeholder={inputKind === "url" ? "Paste a link you're not sure about..." : "Paste the message, DM, email, or offer that feels off..."} aria-label={inputKind === "url" ? "URL to scan" : "Text to scan"} /><div className="textarea-footer"><span>{content.length > 0 ? `${content.length} characters` : "No content is stored by default"}</span><span className="shortcut"><kbd>⌘</kbd><kbd>↵</kbd> scan</span></div></div>}
          <button className="scan-button" onClick={onAnalyze} disabled={isAnalyzing}>{isAnalyzing ? <><span className="button-spinner" /> Reading the receipts...</> : <><WandSparkles size={17} /> Scan for signals <ArrowUpRight size={17} /></>}</button>
          <div className="detector-note"><ShieldAlert size={14} /> <span>Risk indicators are not proof of fraud.</span><span className="note-sep" /> <button onClick={() => window.alert("ScamShield looks for patterns, not personal identity.")}>How it works <ArrowUpRight size={12} /></button></div>
        </div>
        <div className="floating-chip chip-top"><span className="chip-dot coral" /> urgency detected <span>+24</span></div>
        <div className="floating-chip chip-bottom"><span className="chip-dot mint" /> privacy mode <Check size={13} /></div>
      </div>
      <div className="scan-marquee" aria-hidden="true"><span>NO CAPTCHAS</span><i /> <span>NO DATA BROKERED</span><i /> <span>JUST SIGNALS + CONTEXT</span><i /> <span>NO CAPTCHAS</span><i /> <span>NO DATA BROKERED</span></div>
    </section>
  );
}

function UploadZone({ filePreview, fileName, onFileChange, onFileDrop }: { filePreview?: string; fileName?: string; onFileChange: (event: ChangeEvent<HTMLInputElement>) => void; onFileDrop: (file: File) => void }) {
  return <label className={filePreview ? "upload-zone has-file" : "upload-zone"} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const dropped = event.dataTransfer.files[0]; if (dropped) onFileDrop(dropped); }}><input type="file" accept="image/png,image/jpeg,image/webp" onChange={onFileChange} />{filePreview ? <><img src={filePreview} alt="Selected screenshot preview" /><div className="upload-overlay"><CheckCircle2 size={22} /><b>{fileName}</b><span>click to replace</span></div></> : <><span className="upload-icon"><UploadCloud size={23} /></span><b>Drop a screenshot here</b><span>or click to browse · PNG, JPG, WebP · max 5 MB</span><small><FileSearch2 size={13} /> OCR runs in your local FastAPI pipeline; this UI does not retain the image</small></>}</label>;
}

function ResultView({ result, onBack, onNewScan, onToast, lang, t }: { result: ScanResult; onBack: () => void; onNewScan: () => void; onToast: (message: string) => void; lang: "en" | "hi"; t: (key: string) => string }) {
  const [feedback, setFeedback] = useState<boolean | undefined>();
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState<string | undefined>();
  const [animatedScore, setAnimatedScore] = useState(0);
  const [revealStep, setRevealStep] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setAnimatedScore(result.score);
      setRevealStep(3);
      return;
    }
    let frame: number;
    let start = 0;
    const duration = 900;
    const begin = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - begin) / duration);
      setAnimatedScore(Math.floor(t * result.score));
      if (t < 1) frame = requestAnimationFrame(step);
      else setAnimatedScore(result.score);
    };
    frame = requestAnimationFrame(step);
    const revealTimer1 = window.setTimeout(() => setRevealStep(1), 120);
    const revealTimer2 = window.setTimeout(() => setRevealStep(2), 400);
    const revealTimer3 = window.setTimeout(() => setRevealStep(3), 750);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(revealTimer1);
      window.clearTimeout(revealTimer2);
      window.clearTimeout(revealTimer3);
    };
  }, [result]);
  const handleFeedback = async (helpful: boolean) => {
    if (result.mode === "demo") {
      onToast("This is a demo result — feedback is only recorded for real scans.");
      return;
    }
    setFeedback(helpful);
    const delivered = await sendFeedback(result.id, helpful);
    if (!delivered) {
      setFeedback(undefined);
      onToast("Couldn't send that feedback — nothing was recorded.");
      return;
    }
    onToast(helpful ? "Thanks — that helps keep explanations useful." : "Got it. We'll use that signal to improve the read.");
  };
  const copySummary = async () => {
    await navigator.clipboard?.writeText(`${result.verdict}\n${result.summary}`);
    setCopied(true);
    onToast("Verdict copied to clipboard.");
    window.setTimeout(() => setCopied(false), 1800);
  };
  return <section className="slide-frame result-layout">
    <div className="result-head"><button className="back-button" onClick={onBack}><ArrowLeft size={16} /> New scan</button><div className="result-meta"><span><span className="live-dot" /> {result.mode === "demo" ? "demo result" : "analysis complete"}</span><span className="meta-sep" /> {result.createdAt}</div>{result.mode === "demo" && <span className="demo-pill">DEMO DATA — not a live analysis</span>}<button className="copy-button" onClick={copySummary}>{copied ? <Check size={15} /> : <Copy size={15} />} {copied ? "Copied" : "Copy verdict"}</button></div>
    <div className="result-hero">
      <div className="score-orbit"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" />      <div className="score-core"><span>risk score</span><strong>{animatedScore}</strong><small>/ 100</small></div><span className="orbit-label orbit-label-a">signal<br />density</span><span className="orbit-label orbit-label-b">{result.uncertainty} confidence</span></div>
      {revealStep >= 1 && <div className="verdict-copy reveal"><div className={`risk-pill ${result.band}`}><span className="pill-pulse" /> {result.band === "high" ? "high risk" : `${result.band} risk`} <span className="pill-slash">//</span> {result.category}</div><h1>{result.verdict}</h1><p>{result.summary}</p><div className="uncertainty-note"><Info size={15} /><span><b>{result.uncertainty} uncertainty.</b> The score is bounded to the evidence we can see — not a verdict about the sender.</span></div>{result.uncertaintyReasons.length > 0 && <ul className="uncertainty-reasons">{result.uncertaintyReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}</div>}
    {result.band === "high" && revealStep >= 2 && <div className="fraud-alert reveal"><div className="fraud-alert-head"><span className="fraud-alert-icon"><AlertTriangle size={20} />!</span><div><h3>Fraud Warning</h3><p>This message has been flagged as high-risk fraud. Do not reply, click links, or transfer money.</p></div></div><ul className="fraud-alert-points"><li><b>🚨 Immediate action:</b> Call 1930 to report financial fraud</li><li><b>📧 Report online:</b> Visit cybercrime.gov.in</li><li><b>💡 Stay safe:</b> Do not engage with the sender or share OTPs</li></ul></div>}
    </div>
    {revealStep >= 1 && <section className="panel offer-decision reveal"><div className="panel-head"><div><span className="section-label">OFFER DECISION</span><h2>Smart offer analysis</h2></div></div><div className="key-points"><div className="key-points-label">KEY POINTS</div><p className="key-reason">{result.actionVerdict === "REJECT" ? `Rejected because ${result.negativeSignals.length} warning signal${result.negativeSignals.length === 1 ? "" : "s"} outweigh the positives — score ${result.score}/100.` : result.actionVerdict === "SELECT" ? `Looks selectable: ${result.positiveSignals.length} supporting signal${result.positiveSignals.length === 1 ? "" : "s"} and no clear red flags.` : "Uncertain — not enough evidence to select or reject. Verify before acting."}</p><ul>{[...result.negativeSignals, ...result.positiveSignals].slice(0, 3).map((s) => <li key={`${s.type}-${s.id}`}><span className={`kp-tag ${s.type}`}>{s.type === "negative" ? "REJECT" : "SELECT"}</span><b>{s.title}</b> — {s.reason}</li>)}</ul></div><div className="offer-verdict"><div className={`offer-badge ${result.actionVerdict.toLowerCase()}`}><span className="badge-label">{result.actionVerdict === "SELECT" ? t("verdict.select") : result.actionVerdict === "REJECT" ? t("verdict.reject") : t("verdict.verify")}</span></div><div className="offer-meta"><div className="meta-row"><span>{t("label.confidence")}</span><strong>{result.verdictConfidence}</strong></div><div className="meta-row"><span>{t("label.risk-level")}</span><strong>{result.band}</strong></div><div className="meta-row"><span>{t("label.score")}</span><strong>{result.score} / 100</strong></div></div></div><div className="offer-signals"><div className="signal-column positive"><div className="signal-head"><span className="signal-title">{t("section.select")}</span><span className="signal-count">{result.positiveSignals.length}</span></div>        {result.positiveSignals.length === 0 ? <div className="empty-msg">{t("msg.no-signals")}</div> : result.positiveSignals.map((s) => <SignalRow key={s.id} signal={s} t={t} />)}</div><div className="signal-column negative"><div className="signal-head"><span className="signal-title">{t("section.reject")}</span><span className="signal-count">{result.negativeSignals.length}</span></div>{result.negativeSignals.length === 0 ? <div className="empty-msg">{result.actionVerdict === "SELECT" ? "No warning signals detected." : t("msg.no-signals")}</div> : result.negativeSignals.map((s) => <SignalRow key={s.id} signal={s} t={t} />)}</div></div>{result.actionVerdict === "VERIFY" && <div className="verify-note">{t("msg.insufficient")}</div>}</section>}
    {revealStep >= 2 && <div className="result-grid reveal">
      <div className="result-main-column">
        <section className="panel evidence-panel"><div className="panel-head"><div><span className="section-label">01 / THE RECEIPTS</span><h2>Why this got flagged</h2></div><span className="evidence-total">{result.evidence.length} signals <span>·</span> {result.evidence.reduce((sum, item) => sum + item.weight, 0)} pts</span></div><div className="evidence-list">{result.evidence.map((item) => <EvidenceRow key={item.id} item={item} expanded={expanded === item.id} onExpand={() => setExpanded(expanded === item.id ? undefined : item.id)} />)}</div></section>
        <section className="panel recommendation-panel"><div className="panel-head"><div><span className="section-label">02 / YOUR NEXT MOVE</span><h2>Keep it low-risk</h2></div><span className="recommendation-spark"><Sparkles size={15} /> practical, not panic</span></div><div className="recommendations">{result.recommendations.map((recommendation, index) => <div className="recommendation" key={recommendation}><span className="recommendation-number">0{index + 1}</span><p>{recommendation}</p><CheckCircle2 size={17} /></div>)}</div></section>
      </div>
      <aside className="result-side-column"><section className="panel module-panel"><div className="panel-head compact"><div><span className="section-label">SIGNAL MIX</span><h2>Module breakdown</h2></div><BarChart3 size={18} /></div><div className="module-bars">{result.modules.map((module) => <div className="module-row" key={module.name}><div className="module-label"><span>{module.name}</span><b>{module.score}</b></div><div className="module-track"><span className={`module-fill ${module.color}`} style={{ width: `${module.score}%` }} /></div><small>{module.label}</small></div>)}</div></section><section className="panel entities-panel"><div className="panel-head compact"><div><span className="section-label">EXTRACTED CONTEXT</span><h2>Entities found</h2></div><Network size={17} /></div><div className="entity-cloud">{result.entities.map((entity) => <span key={entity}>{entity}</span>)}</div></section><section className="panel privacy-panel"><div className="privacy-mark"><LockKeyhole size={18} /></div><div><span className="section-label">PRIVACY CHECK</span><h3>Nothing spooky behind the scenes.</h3><p>{result.intel.detail}</p></div><CheckCircle2 className="privacy-check" size={17} /></section>      </aside>
    </div>}
    {result.ocrText && revealStep >= 2 && <section className="panel ocr-panel reveal"><div className="panel-head compact"><div><span className="section-label">SCREENSHOT MODE</span><h2>OCR text preview</h2></div><FileSearch2 size={17} /></div><p>{result.ocrText}</p></section>}
    {revealStep >= 3 && <section className="panel fineprint-panel reveal"><div className="panel-head compact"><div><span className="section-label">READ THE FINE PRINT</span><h2>What this score is (and is not)</h2></div><Info size={17} /></div><p className="fineprint-disclaimer">{result.disclaimer}</p><p className="fineprint-note">{result.scoreNote}</p></section>}
    {result.mode !== "demo" && revealStep >= 3 && <section className="panel privacy-panel"><div className="privacy-mark"><Phone size={18} /></div><div><span className="section-label">GOVERNMENT HELPLINE</span><h3>India: 1930 - Cyber Crime Reporting</h3><p>Report financial fraud immediately at 1930 or visit cybercrime.gov.in</p><p>{result.intel.detail || "Keep this number handy for future reference."}</p></div><CheckCircle2 className="privacy-check" size={17} /></section>}
    <div className="result-footer"><div className="feedback"><span>Was this read useful?</span><button className={feedback === true ? "feedback-button selected" : "feedback-button"} onClick={() => handleFeedback(true)}><Check size={14} /> Yep</button><button className={feedback === false ? "feedback-button selected negative" : "feedback-button"} onClick={() => handleFeedback(false)}><Flag size={14} /> Not quite</button></div><button className="text-button" onClick={onNewScan}><RotateCcw size={15} /> Run another scan</button></div>
  </section>;
}

function EvidenceRow({ item, expanded, onExpand }: { item: ScanResult["evidence"][number]; expanded: boolean; onExpand: () => void }) {
  return <button className={expanded ? "evidence-row expanded" : "evidence-row"} onClick={onExpand}><span className={`evidence-icon ${item.tone}`}>{item.tone === "danger" ? <AlertTriangle size={16} /> : item.tone === "warning" ? <Zap size={16} /> : <Check size={16} />}</span><span className="evidence-copy"><span className="evidence-title">{item.title}<em>{item.source}</em></span>{expanded ? <span className="evidence-detail">{item.reason}<code>{item.snippet}</code></span> : <span className="evidence-snippet">{item.snippet}</span>}</span><span className={`weight ${item.tone}`}>+{item.weight}</span><ChevronRight className={expanded ? "chevron rotate" : "chevron"} size={16} /></button>;
}

function SignalRow({ signal, t }: { signal: Signal; t: (key: string) => string }) {
  return (
    <div className={`signal-row ${signal.type}`}>
      <span className={`signal-sev ${signal.severity}`}>{signal.severity}</span>
      <div className="signal-body">
        <div className="signal-title">{signal.title}</div>
        <div className="signal-reason">{signal.reason}</div>
        {signal.evidence && <div className="signal-evidence"><span className="evidence-tag">{t("label.evidence")}</span> {signal.evidence}</div>}
      </div>
    </div>
  );
}

function HistoryView({ items, loaded, onOpen, onDelete, onNewScan }: { items: HistoryItem[]; loaded: boolean; onOpen: (item: HistoryItem) => void; onDelete: (id: string) => void; onNewScan: () => void }) {
  const [pendingDelete, setPendingDelete] = useState<string | undefined>();
  return <section className="slide-frame history-layout"><div className="history-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> YOUR RECEIPTS</div><h1>Scan history, <span className="headline-highlight">no judgment.</span></h1><p>Recent checks live here for 30 days. Raw content is never shown in this list.</p></div><button className="scan-button small" onClick={onNewScan}><ScanLine size={16} /> New scan <ArrowUpRight size={16} /></button></div><div className="history-toolbar"><span><span className="live-dot" /> {loaded ? `${items.length} analyses` : "loading scans..."}</span><span className="retention"><Clock3 size={14} /> auto-expires after 30 days</span></div><div className="history-list">{!loaded ? <div className="empty-state"><span className="button-spinner dark" /> Loading your scans</div> : items.length === 0 ? <div className="empty-state"><Inbox size={22} /> No scans yet. The first one is usually the most useful.</div> : items.map((item) => <div className="history-row" key={item.id}><div className={`history-score ${item.band}`}><strong>{item.score}</strong><span>/100</span></div><div className="history-info"><div><span className={`history-band ${item.band}`}>{item.band} risk</span><span className="history-category">{item.category}</span></div><h3>{item.summary}</h3><p>{item.createdAt} <span>·</span> {item.inputType === "screenshot" ? "screenshot" : item.inputType === "url" ? "URL" : "message"}</p></div><button className="history-open" onClick={() => onOpen(item)}>Open result <ArrowUpRight size={15} /></button>{pendingDelete === item.id ? <div className="delete-confirm"><span>Delete this scan?</span><button onClick={() => { onDelete(item.id); setPendingDelete(undefined); }}>Yes, remove</button><button onClick={() => setPendingDelete(undefined)}>Keep</button></div> : <button className="icon-button delete-button" onClick={() => setPendingDelete(item.id)} aria-label={`Delete scan ${item.id}`}><Trash2 size={16} /></button>}</div>)}</div><div className="privacy-strip"><LockKeyhole size={14} /> <span>Raw message content is <b>never stored</b> in history — only the risk summary, category, and extracted entities.</span><Trash2 size={14} /></div></section>;
}

function ScanningOverlay({ stage, filePreview, inputKind }: { stage: number; filePreview?: string; inputKind: InputKind }) {
  return (
    <div className="scan-overlay">
      <div className="scan-overlay-backdrop" />
      <div className="scan-overlay-body">
        <div className="scan-icon-wrap"><ScanLine size={34} strokeWidth={2} /></div>
        <div className="scan-line" />
        {inputKind === "screenshot" && filePreview && (
          <div className="scan-preview-wrap"><img className="scan-preview" src={filePreview} alt="Scan preview" /><div className="scan-line-overlay" /></div>
        )}
        <div className="scan-status">{SCAN_STAGES[stage]}</div>
        <div className="scan-hint">Analyzing signals — this takes a few seconds.</div>
      </div>
    </div>
  );
}

function Footer() {
  return <footer className="footer"><span>SCAM<span className="wordmark-slash">//</span>SHIELD <span className="footer-muted">is a signal scanner, not a crystal ball.</span></span><span className="footer-right"><span><span className="status-pip" /> all systems nominal</span><span className="footer-sep" /> built for the group chat generation <MousePointer2 size={14} /></span></footer>;
}

export default App;