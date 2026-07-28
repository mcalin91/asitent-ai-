"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Bell,
  CalendarPlus,
  CheckCircle2,
  ClipboardList,
  Download,
  FilePlus2,
  FileText,
  ExternalLink,
  HeartPulse,
  History,
  LayoutDashboard,
  Loader2,
  LocateFixed,
  Menu,
  MapPin,
  MessageCircle,
  Pill,
  RotateCw,
  Settings,
  Sparkles,
  Star,
  Stethoscope,
  Trash2,
  Upload,
  X,
} from "lucide-react";

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL;
const API_URL = configuredApiUrl === "__SAME_ORIGIN__" ? "" : configuredApiUrl || "http://localhost:8000";

type Item = Record<string, any>;
type Screen =
  | "Dashboard"
  | "Dosar Medical"
  | "Analize"
  | "Documente"
  | "Investigatii"
  | "Medicatie"
  | "Istoric Medical"
  | "Monitorizare"
  | "Recomandari AI"
  | "Medici recomandati"
  | "Programari"
  | "Setari"
  | "Notificari";

const nav: { label: Screen; icon: any }[] = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Dosar Medical", icon: ClipboardList },
  { label: "Analize", icon: HeartPulse },
  { label: "Documente", icon: FileText },
  { label: "Investigatii", icon: Stethoscope },
  { label: "Medicatie", icon: Pill },
  { label: "Istoric Medical", icon: History },
  { label: "Monitorizare", icon: HeartPulse },
  { label: "Recomandari AI", icon: Sparkles },
  { label: "Medici recomandati", icon: MapPin },
  { label: "Programari", icon: CalendarPlus },
  { label: "Setari", icon: Settings },
  { label: "Notificari", icon: Bell },
];

const emptyMessages: Record<string, string> = {
  analyses: "Nu exista analize salvate inca.",
  documents: "Nu exista documente incarcate.",
  investigations: "Nu exista investigatii salvate.",
  medications: "Nu exista medicatie salvata.",
  history: "Nu exista istoric medical salvat.",
  monitoring: "Nu exista masuratori salvate.",
  recommendations: "Nu exista recomandari salvate.",
  appointments: "Nu exista programari salvate.",
  notifications: "Nu exista notificari.",
};

async function request(path: string, options: RequestInit = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    let message = "Actiunea nu a putut fi finalizata.";
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

function toDateInput(value?: string) {
  if (!value) return "";
  return value.slice(0, 16);
}

function todayInput() {
  return new Date().toISOString().slice(0, 16);
}

function StatusPill({ status }: { status?: string }) {
  const tone = status === "normal" || status === "programata" ? "good" : status === "crescut" || status === "scazut" || status === "ridicata" ? "warn" : "soft";
  return <span className={`pill ${tone}`}>{status || "salvat"}</span>;
}

function Empty({ label }: { label: string }) {
  return <div className="empty">{emptyMessages[label]}</div>;
}

export default function Home() {
  const [screen, setScreen] = useState<Screen>("Dashboard");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [dashboard, setDashboard] = useState<Item>({});
  const [data, setData] = useState<Record<string, Item[]>>({});
  const [quickQuestions, setQuickQuestions] = useState<string[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState<Item[]>([]);
  const [settings, setSettings] = useState<Item>({});
  const [aiStatus, setAiStatus] = useState<Item>({});
  const [doctorStatus, setDoctorStatus] = useState<Item>({});
  const [doctorResults, setDoctorResults] = useState<Item>({});
  const [doctorLoading, setDoctorLoading] = useState(false);
  const [doctorError, setDoctorError] = useState("");
  const [doctorRadius, setDoctorRadius] = useState("10");

  const documentInput = useRef<HTMLInputElement>(null);
  const analysesInput = useRef<HTMLInputElement>(null);

  const [medication, setMedication] = useState({ name: "", dose: "", frequency: "", instructions: "" });
  const [appointment, setAppointment] = useState({ doctor: "", specialty: "", scheduled_at: todayInput(), location: "", notes: "" });
  const [investigation, setInvestigation] = useState({ title: "", category: "", result: "", performed_at: todayInput() });
  const [historyItem, setHistoryItem] = useState({ title: "", category: "", details: "", event_date: todayInput() });
  const [monitoring, setMonitoring] = useState({ metric: "", value: "", unit: "", notes: "" });

  async function refreshAll() {
    setLoading(true);
    setError("");
    try {
      const [dash, record, qs, appSettings, currentAiStatus, currentDoctorStatus] = await Promise.all([
        request("/dashboard"),
        request("/medical-record"),
        request("/quick-questions"),
        request("/settings"),
        request("/ai/status"),
        request("/doctors/status"),
      ]);
      setDashboard(dash);
      setQuickQuestions(qs);
      setSettings(appSettings);
      setAiStatus(currentAiStatus);
      setDoctorStatus(currentDoctorStatus);
      setData({
        documents: record.documents,
        analyses: record.analyses,
        investigations: record.investigations,
        medications: record.medications,
        history: record.history,
        monitoring: record.monitoring,
        recommendations: record.recommendations,
        appointments: record.appointments,
        notifications: dash.notifications || [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nu pot incarca datele.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshAll();
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }
  }, []);

  const stats = dashboard.stats || {};
  const recentDocuments = dashboard.recent_documents || [];
  const abnormalAnalyses = useMemo(() => (data.analyses || []).filter((item) => item.status !== "normal"), [data.analyses]);

  async function runAction(label: string, action: () => Promise<void>) {
    setSaving(label);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(`${label} finalizat.`);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Actiunea a esuat.");
    } finally {
      setSaving("");
    }
  }

  async function uploadSelected(file: File | undefined, endpoint: string, label: string) {
    if (!file) return;
    const allowed = [".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt", ".csv", ".docx"];
    if (!allowed.some((extension) => file.name.toLowerCase().endsWith(extension))) {
      setError("Tip de fisier neacceptat. Foloseste PDF, JPG, PNG, WebP, TXT, CSV sau DOCX.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Fisierul depaseste limita de 10 MB.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    await runAction(label, async () => {
      await request(endpoint, { method: "POST", body: form });
    });
  }

  async function submitJson(path: string, body: Item, label: string, reset?: () => void) {
    await runAction(label, async () => {
      await request(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      reset?.();
    });
  }

  async function exportRecord() {
    await runAction("Export dosar medical", async () => {
      const response = await fetch(`${API_URL}/medical-record/export`);
      if (!response.ok) throw new Error("Exportul nu a putut fi generat.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "dosar-medical-ai.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  }

  async function sendChat(message = chatInput) {
    if (!message.trim()) return;
    setChat((items) => [...items, { role: "user", content: message }]);
    setChatInput("");
    await runAction("Chat AI", async () => {
      const answer = await request("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      setChat((items) => [...items, { role: "assistant", content: answer.answer }]);
    });
  }

  async function findDoctors() {
    setDoctorLoading(true);
    setDoctorError("");
    if (!doctorStatus.enabled) {
      setDoctorError("Cautarea medicilor nu este configurata pe server.");
      setDoctorLoading(false);
      return;
    }
    if (!navigator.geolocation) {
      setDoctorError("Localizarea nu este disponibila pe acest dispozitiv.");
      setDoctorLoading(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const result = await request(
            `/doctors/recommendations?latitude=${coords.latitude}&longitude=${coords.longitude}&radius_km=${doctorRadius}`,
          );
          setDoctorResults(result);
        } catch (err) {
          setDoctorError(err instanceof Error ? err.message : "Medicii nu au putut fi incarcati.");
        } finally {
          setDoctorLoading(false);
        }
      },
      () => {
        setDoctorError("Permisiunea pentru locatie nu a fost acordata. O poti activa din setarile dispozitivului.");
        setDoctorLoading(false);
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  }

  function chooseDoctor(doctor: Item) {
    setAppointment({
      doctor: doctor.name,
      specialty: doctor.matched_specialties?.[0] || "Medicina interna",
      scheduled_at: todayInput(),
      location: doctor.address || "",
      notes: doctor.place_id ? `Google Place ID: ${doctor.place_id}` : "",
    });
    setScreen("Programari");
    setSuccess("Medicul a fost adaugat in formularul de programare.");
  }

  const isBusy = Boolean(saving);
  const goToScreen = (nextScreen: Screen) => {
    setScreen(nextScreen);
    setMobileMenuOpen(false);
  };

  return (
    <main className="shell">
      <aside className={`sidebar ${mobileMenuOpen ? "mobileOpen" : ""}`}>
        <div className="brand">
          <span className="brandMark">+</span>
          <div>
            <strong>Asistent Medical AI</strong>
            <small>{settings.patient_name || "Pacient demo"}</small>
          </div>
          <button className="sidebarClose" onClick={() => setMobileMenuOpen(false)} aria-label="Inchide meniul">
            <X size={20} />
          </button>
        </div>
        <nav>
          {nav.map(({ label, icon: Icon }) => (
            <button key={label} className={screen === label ? "active" : ""} onClick={() => goToScreen(label)}>
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>
      {mobileMenuOpen && <button className="menuOverlay" aria-label="Inchide meniul" onClick={() => setMobileMenuOpen(false)} />}

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{screen}</h1>
            <p>{abnormalAnalyses.length ? `${abnormalAnalyses.length} valori necesita atentie.` : "Datele curente sunt pregatite pentru consult."}</p>
          </div>
          <div className="topActions">
            <button className="ghost notificationButton" onClick={() => goToScreen("Notificari")}>
              <Bell size={18} /> {stats.unread_notifications || 0}
            </button>
            <button className="primary" onClick={exportRecord} disabled={isBusy}>
              <Download size={18} /> Exporta dosar medical
            </button>
          </div>
        </header>

        {(loading || saving || error || success) && (
          <div className="statusBar">
            {loading && <span><Loader2 className="spin" size={16} /> Se incarca datele...</span>}
            {saving && <span><Loader2 className="spin" size={16} /> {saving}...</span>}
            {error && <span className="error">{error}</span>}
            {success && <span className="success">{success}</span>}
          </div>
        )}

        <input ref={documentInput} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.txt,.csv,.docx" hidden onChange={(event) => uploadSelected(event.target.files?.[0], "/documents", "Analiza OCR/AI")} />
        <input ref={analysesInput} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.txt,.csv,.docx" hidden onChange={(event) => uploadSelected(event.target.files?.[0], "/analyses/upload", "Analiza OCR/AI")} />

        {screen === "Dashboard" && (
          <div className="grid">
            <section className={`aiStatus ${aiStatus.enabled ? "online" : "offline"}`}>
              <Sparkles size={18} />
              <div>
                <strong>{aiStatus.enabled ? "OCR si AI active" : "OCR si AI neconfigurate"}</strong>
                <small>
                  {aiStatus.enabled
                    ? `Documentele sunt analizate cu ${aiStatus.provider} · ${aiStatus.model}.`
                    : "Fisierele text sunt analizate local. Pentru imagini si PDF-uri scanate configureaza GEMINI_API_KEY."}
                </small>
              </div>
            </section>
            <section className="heroBand">
              <div>
                <h2>Dosarul tau medical, pregatit pentru urmatoarea discutie cu medicul.</h2>
                <p>{settings.emergency_notice || "Pentru urgente medicale, suna la 112."}</p>
              </div>
              <div className="heroActions">
                <button className="primary" onClick={() => documentInput.current?.click()} disabled={isBusy}><FilePlus2 size={18} /> Incarca documente</button>
                <button onClick={() => analysesInput.current?.click()} disabled={isBusy}><Upload size={18} /> Incarca analize</button>
                <button onClick={() => goToScreen("Medicatie")}><Pill size={18} /> Adauga medicatie</button>
                <button onClick={() => goToScreen("Programari")}><CalendarPlus size={18} /> Programeaza consultatie</button>
              </div>
            </section>

            <section className="stats">
              <Stat label="Documente" value={stats.documents || 0} />
              <Stat label="Analize" value={stats.analyses || 0} />
              <Stat label="Medicamente" value={stats.medications || 0} />
              <Stat label="Programari" value={stats.appointments || 0} />
            </section>

            <section className="panel">
              <Header title="Analize recente" action="Vezi toate analizele" onClick={() => goToScreen("Analize")} />
              <List items={dashboard.recent_analyses || []} empty="analyses" render={(item) => <AnalysisRow item={item} />} />
            </section>

            <section className="panel">
              <Header title="Documente recente" action="Documente recente" onClick={() => goToScreen("Documente")} />
              <List items={recentDocuments} empty="documents" render={(item) => <DocumentRow item={item} onDelete={() => deleteDocument(item.id)} onDownload={() => downloadDocument(item.id, item.filename)} onRetry={() => reanalyzeDocument(item.id)} />} />
            </section>

            <section className="panel wide">
              <Header title="Recomandari AI" action="Vezi toate recomandarile" onClick={() => goToScreen("Recomandari AI")} />
              <List items={dashboard.recommendations || []} empty="recommendations" render={(item) => <RecommendationRow item={item} onComplete={() => completeRecommendation(item.id)} />} />
            </section>
          </div>
        )}

        {screen === "Dosar Medical" && (
          <section className="panel">
            <Header title="Dosar Medical" action="Exporta dosar medical" onClick={exportRecord} />
            <div className="recordGrid">
              <Stat label="Documente" value={(data.documents || []).length} />
              <Stat label="Analize" value={(data.analyses || []).length} />
              <Stat label="Investigatii" value={(data.investigations || []).length} />
              <Stat label="Istoric" value={(data.history || []).length} />
            </div>
            <List items={(data.history || []).slice(0, 6)} empty="history" render={(item) => <SimpleRow title={item.title} subtitle={`${item.category} - ${toDateInput(item.event_date)}`} />} />
          </section>
        )}

        {screen === "Analize" && (
          <section className="panel">
            <Header title="Analize" action="Incarca analize" onClick={() => analysesInput.current?.click()} />
            <form className="formGrid" onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              submitJson("/analyses", Object.fromEntries(form), "Adaugare analiza", () => event.currentTarget.reset());
            }}>
              <input name="name" placeholder="Nume analiza" required />
              <input name="value" type="number" step="0.01" placeholder="Valoare" required />
              <input name="unit" placeholder="Unitate" />
              <input name="reference_range" placeholder="Interval referinta" />
              <button className="primary" disabled={isBusy}><CheckCircle2 size={18} /> Salveaza analiza</button>
            </form>
            <List items={data.analyses || []} empty="analyses" render={(item) => <AnalysisRow item={item} />} />
          </section>
        )}

        {screen === "Documente" && (
          <section className="panel">
            <Header title="Documente" action="Incarca documente" onClick={() => documentInput.current?.click()} />
            <List items={data.documents || []} empty="documents" render={(item) => <DocumentRow item={item} onDelete={() => deleteDocument(item.id)} onDownload={() => downloadDocument(item.id, item.filename)} onRetry={() => reanalyzeDocument(item.id)} />} />
          </section>
        )}

        {screen === "Investigatii" && (
          <section className="panel">
            <Header title="Investigatii" />
            <form className="formGrid" onSubmit={(event) => {
              event.preventDefault();
              submitJson("/investigations", investigation, "Adaugare investigatie", () => setInvestigation({ title: "", category: "", result: "", performed_at: todayInput() }));
            }}>
              <input value={investigation.title} onChange={(e) => setInvestigation({ ...investigation, title: e.target.value })} placeholder="Titlu investigatie" required />
              <input value={investigation.category} onChange={(e) => setInvestigation({ ...investigation, category: e.target.value })} placeholder="Categorie" />
              <input value={investigation.result} onChange={(e) => setInvestigation({ ...investigation, result: e.target.value })} placeholder="Rezultat" />
              <input type="datetime-local" value={investigation.performed_at} onChange={(e) => setInvestigation({ ...investigation, performed_at: e.target.value })} />
              <button className="primary" disabled={isBusy}><CheckCircle2 size={18} /> Salveaza investigatia</button>
            </form>
            <List items={data.investigations || []} empty="investigations" render={(item) => <SimpleRow title={item.title} subtitle={`${item.category} - ${item.result || item.status}`} />} />
          </section>
        )}

        {screen === "Medicatie" && (
          <section className="panel">
            <Header title="Medicatie" />
            <form className="formGrid" onSubmit={(event) => {
              event.preventDefault();
              submitJson("/medications", medication, "Adaugare medicatie", () => setMedication({ name: "", dose: "", frequency: "", instructions: "" }));
            }}>
              <input value={medication.name} onChange={(e) => setMedication({ ...medication, name: e.target.value })} placeholder="Medicament" required />
              <input value={medication.dose} onChange={(e) => setMedication({ ...medication, dose: e.target.value })} placeholder="Doza" required />
              <input value={medication.frequency} onChange={(e) => setMedication({ ...medication, frequency: e.target.value })} placeholder="Frecventa" required />
              <input value={medication.instructions} onChange={(e) => setMedication({ ...medication, instructions: e.target.value })} placeholder="Instructiuni" />
              <button className="primary" disabled={isBusy}><Pill size={18} /> Adauga medicatie</button>
            </form>
            <List items={data.medications || []} empty="medications" render={(item) => (
              <div className="row">
                <div><strong>{item.name}</strong><small>{item.dose} - {item.frequency} {item.instructions ? `- ${item.instructions}` : ""}</small></div>
                <div className="rowActions">
                  <StatusPill status={item.active ? "activa" : "oprita"} />
                  <button className="iconButton" onClick={() => toggleMedication(item.id)}>OK</button>
                  <button className="iconButton danger" onClick={() => deleteMedication(item.id)}><Trash2 size={16} /></button>
                </div>
              </div>
            )} />
          </section>
        )}

        {screen === "Istoric Medical" && (
          <section className="panel">
            <Header title="Istoric Medical" />
            <form className="formGrid" onSubmit={(event) => {
              event.preventDefault();
              submitJson("/history", historyItem, "Adaugare istoric", () => setHistoryItem({ title: "", category: "", details: "", event_date: todayInput() }));
            }}>
              <input value={historyItem.title} onChange={(e) => setHistoryItem({ ...historyItem, title: e.target.value })} placeholder="Eveniment medical" required />
              <input value={historyItem.category} onChange={(e) => setHistoryItem({ ...historyItem, category: e.target.value })} placeholder="Categorie" />
              <input value={historyItem.details} onChange={(e) => setHistoryItem({ ...historyItem, details: e.target.value })} placeholder="Detalii" />
              <input type="datetime-local" value={historyItem.event_date} onChange={(e) => setHistoryItem({ ...historyItem, event_date: e.target.value })} />
              <button className="primary" disabled={isBusy}><CheckCircle2 size={18} /> Salveaza in istoric</button>
            </form>
            <List items={data.history || []} empty="history" render={(item) => <SimpleRow title={item.title} subtitle={`${item.category} - ${item.details || toDateInput(item.event_date)}`} />} />
          </section>
        )}

        {screen === "Monitorizare" && (
          <section className="panel">
            <Header title="Monitorizare" />
            <form className="formGrid" onSubmit={(event) => {
              event.preventDefault();
              submitJson("/monitoring", { ...monitoring, value: Number(monitoring.value) }, "Adaugare masuratoare", () => setMonitoring({ metric: "", value: "", unit: "", notes: "" }));
            }}>
              <input value={monitoring.metric} onChange={(e) => setMonitoring({ ...monitoring, metric: e.target.value })} placeholder="Indicator" required />
              <input value={monitoring.value} onChange={(e) => setMonitoring({ ...monitoring, value: e.target.value })} type="number" step="0.01" placeholder="Valoare" required />
              <input value={monitoring.unit} onChange={(e) => setMonitoring({ ...monitoring, unit: e.target.value })} placeholder="Unitate" />
              <input value={monitoring.notes} onChange={(e) => setMonitoring({ ...monitoring, notes: e.target.value })} placeholder="Observatii" />
              <button className="primary" disabled={isBusy}><HeartPulse size={18} /> Salveaza masuratoare</button>
            </form>
            <List items={data.monitoring || []} empty="monitoring" render={(item) => <SimpleRow title={`${item.metric}: ${item.value} ${item.unit || ""}`} subtitle={item.notes || toDateInput(item.measured_at)} status={item.status} />} />
          </section>
        )}

        {screen === "Recomandari AI" && (
          <section className="panel">
            <Header title="Recomandari AI" action="Vezi toate recomandarile" onClick={() => refreshAll()} />
            <List items={data.recommendations || []} empty="recommendations" render={(item) => <RecommendationRow item={item} onComplete={() => completeRecommendation(item.id)} />} />
          </section>
        )}

        {screen === "Medici recomandati" && (
          <section className="panel">
            <Header title="Medici recomandati" />
            <div className="doctorToolbar">
              <label>
                Raza
                <select value={doctorRadius} onChange={(event) => setDoctorRadius(event.target.value)}>
                  <option value="5">5 km</option>
                  <option value="10">10 km</option>
                  <option value="25">25 km</option>
                  <option value="50">50 km</option>
                </select>
              </label>
              <button className="primary" onClick={findDoctors} disabled={doctorLoading || !doctorStatus.enabled}>
                {doctorLoading ? <Loader2 className="spin" size={18} /> : <LocateFixed size={18} />}
                Gaseste medici in apropiere
              </button>
            </div>
            {!doctorStatus.enabled && (
              <div className="empty">Cautarea necesita configurarea Google Places pe backend.</div>
            )}
            {doctorError && <div className="error doctorMessage">{doctorError}</div>}
            {(doctorResults.recommended_specialties || []).length > 0 && (
              <div className="specialtyReasons">
                {doctorResults.recommended_specialties.map((item: Item) => (
                  <span key={item.specialty}><strong>{item.specialty}</strong><small>{item.reason}</small></span>
                ))}
              </div>
            )}
            {(doctorResults.doctors || []).length > 0 && (
              <>
                <p className="sourceNotice">{doctorResults.ranking_note}</p>
                <div className="doctorGrid">
                  {doctorResults.doctors.map((doctor: Item) => (
                    <article className="doctorCard" key={doctor.place_id}>
                      <div className="doctorCardHeader">
                        <div>
                          <h3>{doctor.name}</h3>
                          <p><MapPin size={15} /> {doctor.distance_km ?? "?"} km · {doctor.address}</p>
                        </div>
                        {doctor.rating && <span className="rating"><Star size={15} /> {doctor.rating} <small>({doctor.review_count})</small></span>}
                      </div>
                      <div className="doctorMeta">
                        {(doctor.matched_specialties || []).map((specialty: string) => <StatusPill key={specialty} status={specialty} />)}
                        {doctor.open_now === true && <StatusPill status="deschis" />}
                      </div>
                      {(doctor.reviews || []).map((review: Item, index: number) => (
                        <blockquote key={`${doctor.place_id}-${index}`}>
                          <strong>{review.author} · {review.rating}/5</strong>
                          <span>{review.text}</span>
                          <small>{review.relative_time}</small>
                        </blockquote>
                      ))}
                      <div className="doctorActions">
                        <button className="primary" onClick={() => chooseDoctor(doctor)}><CalendarPlus size={17} /> Programeaza-te</button>
                        {doctor.google_maps_uri && (
                          <a href={doctor.google_maps_uri} target="_blank" rel="noreferrer"><ExternalLink size={16} /> Google Maps</a>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
                <p className="sourceNotice">{doctorResults.reviews_note} Verifica profilul si acreditarile medicului inainte de programare.</p>
              </>
            )}
          </section>
        )}

        {screen === "Programari" && (
          <section className="panel">
            <Header title="Programari" />
            <form className="formGrid" onSubmit={(event) => {
              event.preventDefault();
              submitJson("/appointments", appointment, "Programare consultatie", () => setAppointment({ doctor: "", specialty: "", scheduled_at: todayInput(), location: "", notes: "" }));
            }}>
              <input value={appointment.doctor} onChange={(e) => setAppointment({ ...appointment, doctor: e.target.value })} placeholder="Medic" required />
              <input value={appointment.specialty} onChange={(e) => setAppointment({ ...appointment, specialty: e.target.value })} placeholder="Specialitate" required />
              <input type="datetime-local" value={appointment.scheduled_at} onChange={(e) => setAppointment({ ...appointment, scheduled_at: e.target.value })} required />
              <input value={appointment.location} onChange={(e) => setAppointment({ ...appointment, location: e.target.value })} placeholder="Locatie" />
              <button className="primary" disabled={isBusy}><CalendarPlus size={18} /> Programeaza consultatie</button>
            </form>
            <List items={data.appointments || []} empty="appointments" render={(item) => (
              <div className="row">
                <div><strong>{item.specialty}</strong><small>{item.doctor} - {toDateInput(item.scheduled_at)} {item.location ? `- ${item.location}` : ""}</small></div>
                <button className="iconButton danger" onClick={() => deleteAppointment(item.id)}><Trash2 size={16} /></button>
              </div>
            )} />
          </section>
        )}

        {screen === "Setari" && (
          <section className="panel">
            <Header title="Setari" />
            <form className="formGrid" onSubmit={(event) => {
              event.preventDefault();
              runAction("Salvare setari", async () => {
                await fetch(`${API_URL}/settings`, {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(settings),
                }).then(async (response) => {
                  if (!response.ok) throw new Error((await response.json()).detail || "Setarile nu au fost salvate.");
                });
              });
            }}>
              <input value={settings.patient_name || ""} onChange={(e) => setSettings({ ...settings, patient_name: e.target.value })} placeholder="Nume pacient" required />
              <input value={settings.language || "ro"} onChange={(e) => setSettings({ ...settings, language: e.target.value })} placeholder="Limba" />
              <label className="toggle"><input type="checkbox" checked={Boolean(settings.notifications_enabled)} onChange={(e) => setSettings({ ...settings, notifications_enabled: e.target.checked })} /> Notificari active</label>
              <input value={settings.emergency_notice || ""} onChange={(e) => setSettings({ ...settings, emergency_notice: e.target.value })} placeholder="Mesaj urgenta" />
              <button className="primary" disabled={isBusy}><CheckCircle2 size={18} /> Salveaza setari</button>
            </form>
          </section>
        )}

        {screen === "Notificari" && (
          <section className="panel">
            <Header title="Notificari" />
            <List items={data.notifications || []} empty="notifications" render={(item) => (
              <div className="row">
                <div><strong>{item.title}</strong><small>{item.body}</small></div>
                <button className="iconButton" onClick={() => markNotificationRead(item.id)}>{item.read ? "Citit" : "Marcheaza"}</button>
              </div>
            )} />
          </section>
        )}
      </section>

      <aside className="chatPanel">
        <div className="chatHeader"><MessageCircle size={18} /> Chat AI</div>
        <div className="quickQuestions">
          {quickQuestions.map((question) => (
            <button key={question} onClick={() => sendChat(question)} disabled={isBusy}>{question}</button>
          ))}
        </div>
        <div className="messages">
          {chat.length === 0 && <div className="empty">Pune o intrebare despre dosarul salvat.</div>}
          {chat.map((message, index) => <div key={index} className={`message ${message.role}`}>{message.content}</div>)}
        </div>
        <form className="chatForm" onSubmit={(event) => { event.preventDefault(); sendChat(); }}>
          <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Scrie intrebarea..." />
          <button className="primary" disabled={isBusy || !chatInput.trim()}><MessageCircle size={18} /></button>
        </form>
      </aside>

      <nav className="mobileBottomNav" aria-label="Navigatie principala">
        <button className={screen === "Dashboard" ? "active" : ""} onClick={() => goToScreen("Dashboard")}>
          <LayoutDashboard size={21} />
          <span>Acasa</span>
        </button>
        <button className={screen === "Dosar Medical" ? "active" : ""} onClick={() => goToScreen("Dosar Medical")}>
          <ClipboardList size={21} />
          <span>Dosar</span>
        </button>
        <button className="mobileUpload" onClick={() => documentInput.current?.click()} disabled={isBusy} aria-label="Incarca document">
          <Upload size={24} />
          <span>Incarca</span>
        </button>
        <button className={screen === "Medici recomandati" ? "active" : ""} onClick={() => goToScreen("Medici recomandati")}>
          <MapPin size={21} />
          <span>Medici</span>
        </button>
        <button onClick={() => setMobileMenuOpen(true)}>
          <Menu size={21} />
          <span>Meniu</span>
        </button>
      </nav>
    </main>
  );

  async function deleteDocument(id: number) {
    if (!confirm("Stergi documentul din dosarul medical?")) return;
    await runAction("Stergere document", async () => {
      await request(`/documents/${id}`, { method: "DELETE" });
    });
  }

  async function reanalyzeDocument(id: number) {
    await runAction("Reanaliza OCR/AI", async () => {
      await request(`/documents/${id}/reanalyze`, { method: "POST" });
    });
  }

  async function downloadDocument(id: number, filename: string) {
    await runAction("Descarcare document", async () => {
      const response = await fetch(`${API_URL}/documents/${id}/download`);
      if (!response.ok) throw new Error("Documentul nu a putut fi descarcat.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  async function deleteMedication(id: number) {
    if (!confirm("Stergi medicamentul din lista?")) return;
    await runAction("Stergere medicatie", async () => {
      await request(`/medications/${id}`, { method: "DELETE" });
    });
  }

  async function toggleMedication(id: number) {
    await runAction("Actualizare medicatie", async () => {
      await request(`/medications/${id}/toggle`, { method: "PATCH" });
    });
  }

  async function completeRecommendation(id: number) {
    await runAction("Finalizare recomandare", async () => {
      await request(`/recommendations/${id}/complete`, { method: "PATCH" });
    });
  }

  async function deleteAppointment(id: number) {
    if (!confirm("Anulezi programarea?")) return;
    await runAction("Anulare programare", async () => {
      await request(`/appointments/${id}`, { method: "DELETE" });
    });
  }

  async function markNotificationRead(id: number) {
    await runAction("Actualizare notificare", async () => {
      await request(`/notifications/${id}/read`, { method: "PATCH" });
    });
  }
}

function Header({ title, action, onClick }: { title: string; action?: string; onClick?: () => void }) {
  return (
    <div className="sectionHeader">
      <h2>{title}</h2>
      {action && <button onClick={onClick}>{action}</button>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}

function List({ items, empty, render }: { items: Item[]; empty: string; render: (item: Item) => ReactNode }) {
  if (!items?.length) return <Empty label={empty} />;
  return <div className="list">{items.map((item) => <div key={item.id}>{render(item)}</div>)}</div>;
}

function AnalysisRow({ item }: { item: Item }) {
  return (
    <div className="row">
      <div>
        <strong>{item.name}</strong>
        <small>{item.value} {item.unit} {item.reference_range ? `- referinta ${item.reference_range}` : ""}</small>
      </div>
      <StatusPill status={item.status} />
    </div>
  );
}

function DocumentRow({ item, onDelete, onDownload, onRetry }: { item: Item; onDelete: () => void; onDownload: () => void; onRetry: () => void }) {
  const status = item.analysis_status === "completed"
    ? item.analysis_provider === "gemini" ? "Gemini" : item.analysis_provider === "openai" ? "OpenAI" : "local"
    : item.analysis_status === "processing" ? "procesare"
    : item.analysis_status === "needs_ai" ? "necesita AI"
    : item.analysis_status === "failed" ? "eroare" : "salvat";
  return (
    <div className="row">
      <div>
        <strong>{item.filename}</strong>
        <small>{item.analysis_summary || `${Math.round((item.size || 0) / 1024)} KB`}</small>
      </div>
      <div className="rowActions">
        <StatusPill status={status} />
        {(item.analysis_status === "failed" || item.analysis_status === "needs_ai") && (
          <button className="iconButton" title="Reanalizeaza cu OCR/AI" onClick={onRetry}><RotateCw size={16} /></button>
        )}
        <button className="iconButton" title="Descarca documentul" onClick={onDownload}><Download size={16} /></button>
        <button className="iconButton danger" onClick={onDelete}><Trash2 size={16} /></button>
      </div>
    </div>
  );
}

function RecommendationRow({ item, onComplete }: { item: Item; onComplete: () => void }) {
  return (
    <div className="row">
      <div>
        <strong>{item.title}</strong>
        <small>{item.body}</small>
      </div>
      <div className="rowActions">
        <StatusPill status={item.priority} />
        {!item.completed && <button className="iconButton" onClick={onComplete}>OK</button>}
      </div>
    </div>
  );
}

function SimpleRow({ title, subtitle, status }: { title: string; subtitle?: string; status?: string }) {
  return (
    <div className="row">
      <div>
        <strong>{title}</strong>
        {subtitle && <small>{subtitle}</small>}
      </div>
      {status && <StatusPill status={status} />}
    </div>
  );
}
