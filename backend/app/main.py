import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .ai_service import (
    MedicalDocumentResult,
    ai_enabled,
    analyze_with_ai,
    chat_with_ai,
    configured_model,
    configured_provider,
    extract_local_text,
)
from .doctor_service import places_enabled, recommend_specialties, search_doctors


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "medical_ai.sqlite3"))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    with connect() as db:
        cur = db.execute(sql, params)
        db.commit()
        return int(cur.lastrowid)


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as db:
        return rows_to_dicts(db.execute(sql, params).fetchall())


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with connect() as db:
        return row_to_dict(db.execute(sql, params).fetchone())


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'document',
                mime_type TEXT NOT NULL DEFAULT 'text/plain',
                size INTEGER NOT NULL DEFAULT 0,
                content TEXT NOT NULL DEFAULT '',
                analysis_summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT '',
                reference_range TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'normal',
                notes TEXT NOT NULL DEFAULT '',
                source_document_id INTEGER,
                measured_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(source_document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS investigations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                result TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'in_urmarire',
                performed_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dose TEXT NOT NULL,
                frequency TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL DEFAULT '',
                instructions TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'medical',
                details TEXT NOT NULL DEFAULT '',
                event_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monitoring (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'normal',
                measured_at TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medie',
                source TEXT NOT NULL DEFAULT 'AI demo',
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor TEXT NOT NULL,
                specialty TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'programata',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'info',
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        document_columns = {row["name"] for row in db.execute("PRAGMA table_info(documents)").fetchall()}
        for column, definition in {
            "analysis_status": "TEXT NOT NULL DEFAULT 'pending'",
            "analysis_provider": "TEXT NOT NULL DEFAULT 'local'",
            "analysis_model": "TEXT NOT NULL DEFAULT ''",
            "analysis_error": "TEXT NOT NULL DEFAULT ''",
            "analysis_confidence": "REAL NOT NULL DEFAULT 0",
            "storage_path": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if column not in document_columns:
                db.execute(f"ALTER TABLE documents ADD COLUMN {column} {definition}")
        db.commit()
    seed_demo_data()


def table_count(table: str) -> int:
    row = fetch_one(f"SELECT COUNT(*) AS total FROM {table}")
    return int(row["total"] if row else 0)


def seed_demo_data() -> None:
    if table_count("settings") == 0:
        defaults = {
            "patient_name": "Pacient demo",
            "language": "ro",
            "notifications_enabled": "true",
            "emergency_notice": "Pentru durere toracica, dificultati de respiratie, confuzie brusca sau simptome severe, suna la 112.",
        }
        for key, value in defaults.items():
            execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    if table_count("monitoring") == 0:
        for metric, value, unit, status in [
            ("Tensiune sistolica", 138, "mmHg", "atentie"),
            ("Puls", 76, "bpm", "normal"),
            ("Greutate", 82, "kg", "normal"),
        ]:
            execute(
                "INSERT INTO monitoring (metric, value, unit, status, measured_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (metric, value, unit, status, now_iso(), now_iso()),
            )

    if table_count("recommendations") == 0:
        execute(
            "INSERT INTO recommendations (title, body, priority, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "Discuta rezultatele metabolice cu medicul",
                "Valorile demo sugereaza ca merita verificata glicemia, profilul lipidic si stilul de viata la urmatoarea consultatie.",
                "medie",
                "AI demo",
                now_iso(),
            ),
        )


class AnalysisIn(BaseModel):
    name: str = Field(min_length=2)
    value: float
    unit: str = ""
    reference_range: str = ""
    status: str = "normal"
    notes: str = ""
    measured_at: str = Field(default_factory=now_iso)


class InvestigationIn(BaseModel):
    title: str = Field(min_length=2)
    category: str = "general"
    result: str = ""
    status: str = "in_urmarire"
    performed_at: str = Field(default_factory=now_iso)


class MedicationIn(BaseModel):
    name: str = Field(min_length=2)
    dose: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    start_date: str = Field(default_factory=now_iso)
    end_date: str = ""
    instructions: str = ""
    active: bool = True


class HistoryIn(BaseModel):
    title: str = Field(min_length=2)
    category: str = "medical"
    details: str = ""
    event_date: str = Field(default_factory=now_iso)


class MonitoringIn(BaseModel):
    metric: str = Field(min_length=2)
    value: float
    unit: str = ""
    status: str = "normal"
    measured_at: str = Field(default_factory=now_iso)
    notes: str = ""


class RecommendationIn(BaseModel):
    title: str = Field(min_length=2)
    body: str = Field(min_length=5)
    priority: str = "medie"
    source: str = "manual"


class AppointmentIn(BaseModel):
    doctor: str = Field(min_length=2)
    specialty: str = Field(min_length=2)
    scheduled_at: str
    location: str = ""
    notes: str = ""
    status: str = "programata"


class SettingsIn(BaseModel):
    patient_name: str = Field(min_length=2)
    language: str = "ro"
    notifications_enabled: bool = True
    emergency_notice: str = ""


class ChatIn(BaseModel):
    message: str = Field(min_length=2)


ANALYSIS_RULES: dict[str, dict[str, Any]] = {
    "glicemie": {"unit": "mg/dL", "range": "70-99", "high": 100, "label": "Glicemie"},
    "hba1c": {"unit": "%", "range": "< 5.7", "high": 5.7, "label": "HbA1c"},
    "ldl": {"unit": "mg/dL", "range": "< 100", "high": 100, "label": "LDL colesterol"},
    "hdl": {"unit": "mg/dL", "range": "> 40", "low": 40, "label": "HDL colesterol"},
    "trigliceride": {"unit": "mg/dL", "range": "< 150", "high": 150, "label": "Trigliceride"},
    "vitamina d": {"unit": "ng/mL", "range": "30-100", "low": 30, "label": "Vitamina D"},
    "tsh": {"unit": "mIU/L", "range": "0.4-4.0", "high": 4, "low": 0.4, "label": "TSH"},
    "creatinina": {"unit": "mg/dL", "range": "0.6-1.2", "high": 1.2, "low": 0.6, "label": "Creatinina"},
    "hemoglobina": {"unit": "g/dL", "range": "12-17", "high": 17, "low": 12, "label": "Hemoglobina"},
}


def classify(name: str, value: float) -> tuple[str, str, str]:
    rule = ANALYSIS_RULES.get(name.lower(), {})
    status = "normal"
    if "high" in rule and value >= float(rule["high"]):
        status = "crescut"
    if "low" in rule and value < float(rule["low"]):
        status = "scazut"
    return status, rule.get("unit", ""), rule.get("range", "")


def analyze_medical_text(text: str, document_id: int | None = None) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    normalized = text.lower().replace(",", ".")
    pattern = re.compile(r"(glicemie|hba1c|ldl|hdl|trigliceride|vitamina\s+d|tsh|creatinina|hemoglobina)\D{0,25}(\d+(?:\.\d+)?)")
    for match in pattern.finditer(normalized):
        key = " ".join(match.group(1).split())
        value = float(match.group(2))
        status, unit, reference = classify(key, value)
        label = ANALYSIS_RULES.get(key, {}).get("label", key.title())
        analysis_id = execute(
            """
            INSERT INTO analyses (name, value, unit, reference_range, status, notes, source_document_id, measured_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (label, value, unit, reference, status, "Extras automat din document.", document_id, now_iso(), now_iso()),
        )
        found.append({"id": analysis_id, "name": label, "value": value, "unit": unit, "reference_range": reference, "status": status})

    alerts = [item for item in found if item["status"] != "normal"]
    if alerts:
        title = "Analize care necesita atentie"
        body = "Au fost gasite valori in afara intervalelor uzuale: " + ", ".join(f"{a['name']} {a['value']} {a['unit']}".strip() for a in alerts)
        execute("INSERT INTO recommendations (title, body, priority, source, created_at) VALUES (?, ?, ?, ?, ?)", (title, body, "ridicata", "Analiza document", now_iso()))
        execute("INSERT INTO notifications (title, body, type, created_at) VALUES (?, ?, ?, ?)", (title, body, "warning", now_iso()))

    summary = (
        f"Au fost extrase {len(found)} valori medicale. "
        f"{len(alerts)} necesita discutie cu medicul." if found else "Document salvat. Nu am gasit automat valori standardizate in text."
    )
    return {"summary": summary, "analyses": found, "alerts": alerts}


def persist_ai_result(result: MedicalDocumentResult, document_id: int) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    for item in result.analyses:
        analysis_id = execute(
            """
            INSERT INTO analyses (name, value, unit, reference_range, status, notes, source_document_id, measured_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.name,
                item.value,
                item.unit,
                item.reference_range,
                item.status,
                item.notes or "Extras cu OCR/AI din document.",
                document_id,
                item.measured_at or result.document_date or now_iso(),
                now_iso(),
            ),
        )
        found.append({"id": analysis_id, **item.model_dump()})

    for recommendation in result.recommendations[:5]:
        execute(
            "INSERT INTO recommendations (title, body, priority, source, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Subiect de discutat cu medicul", recommendation, "medie", "Analiza OCR/AI", now_iso()),
        )

    if result.alerts:
        body = " ".join(result.alerts[:5])
        execute(
            "INSERT INTO notifications (title, body, type, created_at) VALUES (?, ?, ?, ?)",
            ("Document medical analizat", body, "warning", now_iso()),
        )
    return {"summary": result.summary, "analyses": found, "alerts": result.alerts}


app = FastAPI(title="Asistent Medical AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,capacitor://localhost,http://localhost").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": now_iso()}


@app.get("/ai/status")
def ai_status() -> dict[str, Any]:
    return {
        "enabled": ai_enabled(),
        "provider": configured_provider() if ai_enabled() else "local",
        "model": configured_model() if ai_enabled() else "",
        "ocr": ai_enabled(),
        "supported_types": ["application/pdf", "image/jpeg", "image/png", "image/webp", "text/plain", "text/csv", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    }


@app.get("/doctors/status")
def doctors_status() -> dict[str, Any]:
    return {
        "enabled": places_enabled(),
        "provider": "Google Places" if places_enabled() else "",
        "location_required": True,
        "reviews_source": "Google Maps",
    }


@app.get("/doctors/recommendations")
def doctor_recommendations(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=10, ge=1, le=50),
    specialty: str = Query(default="", max_length=80),
) -> dict[str, Any]:
    recommended = recommend_specialties(list_analyses()[:30], list_recommendations()[:20])
    specialties = [specialty.strip()] if specialty.strip() else [item["specialty"] for item in recommended]
    if not places_enabled():
        raise HTTPException(
            status_code=503,
            detail="Cautarea medicilor necesita GOOGLE_PLACES_API_KEY pe backend.",
        )
    try:
        doctors = search_doctors(latitude, longitude, radius_km, specialties)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Google Places nu a putut returna medicii momentan.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Serviciul de cautare a medicilor nu este disponibil momentan.") from exc
    return {
        "recommended_specialties": recommended,
        "doctors": doctors,
        "radius_km": radius_km,
        "ranking_note": "Rezultatele sunt ordonate dupa rating, numarul de recenzii si distanta. Cautarea Google ia in calcul relevanta, distanta si notorietatea.",
        "reviews_note": "Recenziile Google sunt ordonate dupa relevanta si nu reprezinta o verificare medicala a calitatii serviciilor.",
    }


@app.get("/inventory")
def inventory() -> dict[str, Any]:
    screens = [
        "Dashboard",
        "Dosar Medical",
        "Analize",
        "Documente",
        "Investigatii",
        "Medicatie",
        "Istoric Medical",
        "Monitorizare",
        "Recomandari AI",
        "Programari",
        "Setari",
    ]
    actions = [
        "Incarca documente",
        "Incarca analize",
        "Adauga medicatie",
        "Programeaza consultatie",
        "Exporta dosar medical",
        "Vezi toate analizele",
        "Vezi toate recomandarile",
        "Documente recente",
        "Notificari",
        "Chat AI",
        "Intrebari rapide",
    ]
    return {"screens": screens, "actions": actions}


@app.get("/dashboard")
def dashboard() -> dict[str, Any]:
    analyses = fetch_all("SELECT * FROM analyses ORDER BY created_at DESC LIMIT 5")
    documents = fetch_all("SELECT id, filename, kind, mime_type, size, analysis_summary, analysis_status, analysis_provider, analysis_model, analysis_error, analysis_confidence, created_at FROM documents ORDER BY created_at DESC LIMIT 5")
    recommendations = fetch_all("SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 5")
    appointments = fetch_all("SELECT * FROM appointments ORDER BY scheduled_at ASC LIMIT 5")
    notifications = fetch_all("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 5")
    stats = {
        "documents": table_count("documents"),
        "analyses": table_count("analyses"),
        "medications": table_count("medications"),
        "appointments": table_count("appointments"),
        "unread_notifications": len([n for n in notifications if not n["read"]]),
    }
    return {
        "stats": stats,
        "recent_analyses": analyses,
        "recent_documents": documents,
        "recommendations": recommendations,
        "appointments": appointments,
        "notifications": notifications,
    }


@app.get("/medical-record")
def medical_record() -> dict[str, Any]:
    return {
        "settings": get_settings(),
        "documents": list_documents(),
        "analyses": list_analyses(),
        "investigations": list_investigations(),
        "medications": list_medications(),
        "history": list_history(),
        "monitoring": list_monitoring(),
        "recommendations": list_recommendations(),
        "appointments": list_appointments(),
        "exported_at": now_iso(),
    }


@app.get("/medical-record/export")
def export_medical_record() -> JSONResponse:
    return JSONResponse(
        medical_record(),
        headers={"Content-Disposition": 'attachment; filename="dosar-medical-ai.json"'},
    )


@app.get("/documents")
def list_documents() -> list[dict[str, Any]]:
    return fetch_all("SELECT id, filename, kind, mime_type, size, analysis_summary, analysis_status, analysis_provider, analysis_model, analysis_error, analysis_confidence, created_at FROM documents ORDER BY created_at DESC")


@app.get("/documents/recent")
def recent_documents() -> list[dict[str, Any]]:
    return fetch_all("SELECT id, filename, kind, mime_type, size, analysis_summary, analysis_status, analysis_provider, analysis_model, analysis_error, analysis_confidence, created_at FROM documents ORDER BY created_at DESC LIMIT 5")


@app.post("/documents")
async def upload_document(file: UploadFile = File(...), kind: str = "document") -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Fisierul este gol.")
    max_size = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
    if len(raw) > max_size:
        raise HTTPException(status_code=413, detail=f"Fisierul depaseste limita de {max_size // 1024 // 1024} MB.")
    filename = Path(file.filename or "document").name
    mime_type = (file.content_type or "application/octet-stream").lower()
    allowed = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/plain",
        "text/csv",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if mime_type not in allowed:
        raise HTTPException(status_code=415, detail="Tip de fisier neacceptat. Foloseste PDF, JPG, PNG, WebP, TXT, CSV sau DOCX.")
    content = extract_local_text(raw, filename, mime_type)
    storage_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    storage_path.write_bytes(raw)
    doc_id = execute(
        """
        INSERT INTO documents
        (filename, kind, mime_type, size, content, analysis_summary, analysis_status, analysis_provider, storage_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (filename, kind, mime_type, len(raw), content, "", "processing", configured_provider() if ai_enabled() else "local", str(storage_path), now_iso()),
    )
    try:
        if ai_enabled():
            ai_result = analyze_with_ai(raw, filename, mime_type, content)
            result = persist_ai_result(ai_result.result, doc_id)
            stored_content = ai_result.result.extracted_text or content
            execute(
                """
                UPDATE documents SET content = ?, analysis_summary = ?, analysis_status = 'completed',
                analysis_provider = ?, analysis_model = ?, analysis_error = '', analysis_confidence = ?
                WHERE id = ?
                """,
                (stored_content, result["summary"], ai_result.provider, ai_result.model, ai_result.result.confidence, doc_id),
            )
            return {"id": doc_id, "filename": filename, "analysis_status": "completed", "provider": ai_result.provider, "model": ai_result.model, **result}

        if not content:
            message = "OCR/AI necesita cheia furnizorului AI configurat pentru imagini si PDF-uri scanate."
            execute(
                "UPDATE documents SET analysis_summary = ?, analysis_status = 'needs_ai', analysis_error = ? WHERE id = ?",
                (message, message, doc_id),
            )
            raise HTTPException(status_code=503, detail=message)

        result = analyze_medical_text(content, doc_id)
        execute(
            "UPDATE documents SET analysis_summary = ?, analysis_status = 'completed', analysis_provider = 'local' WHERE id = ?",
            (result["summary"], doc_id),
        )
        return {"id": doc_id, "filename": filename, "analysis_status": "completed", "provider": "local", **result}
    except HTTPException:
        raise
    except Exception as exc:
        message = "Analiza OCR/AI nu a putut fi finalizata."
        execute(
            "UPDATE documents SET analysis_summary = ?, analysis_status = 'failed', analysis_error = ? WHERE id = ?",
            (message, str(exc)[:500], doc_id),
        )
        raise HTTPException(status_code=502, detail=f"{message} Incearca din nou sau verifica configurarea OpenAI.") from exc


@app.post("/documents/{document_id}/reanalyze")
def reanalyze_document(document_id: int) -> dict[str, Any]:
    document = fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not document:
        raise HTTPException(status_code=404, detail="Documentul nu exista.")
    if not ai_enabled():
        raise HTTPException(status_code=503, detail="Configureaza cheia furnizorului AI pentru analiza OCR/AI.")
    storage_path = Path(document["storage_path"]) if document.get("storage_path") else None
    if not storage_path or not storage_path.is_file():
        raise HTTPException(status_code=409, detail="Fisierul original nu este disponibil pentru reanalizare.")

    execute("UPDATE documents SET analysis_status = 'processing', analysis_error = '' WHERE id = ?", (document_id,))
    try:
        raw = storage_path.read_bytes()
        local_text = extract_local_text(raw, document["filename"], document["mime_type"])
        ai_result = analyze_with_ai(raw, document["filename"], document["mime_type"], local_text)
        execute("DELETE FROM analyses WHERE source_document_id = ?", (document_id,))
        result = persist_ai_result(ai_result.result, document_id)
        execute(
            """
            UPDATE documents SET content = ?, analysis_summary = ?, analysis_status = 'completed',
            analysis_provider = ?, analysis_model = ?, analysis_error = '', analysis_confidence = ?
            WHERE id = ?
            """,
            (
                ai_result.result.extracted_text or local_text,
                result["summary"],
                ai_result.provider,
                ai_result.model,
                ai_result.result.confidence,
                document_id,
            ),
        )
        return {"id": document_id, "analysis_status": "completed", "provider": ai_result.provider, "model": ai_result.model, **result}
    except Exception as exc:
        execute(
            "UPDATE documents SET analysis_status = 'failed', analysis_error = ? WHERE id = ?",
            (str(exc)[:500], document_id),
        )
        raise HTTPException(status_code=502, detail="Reanalizarea OCR/AI a esuat.") from exc


@app.get("/documents/{document_id}/download")
def download_document(document_id: int) -> FileResponse:
    document = fetch_one("SELECT filename, mime_type, storage_path FROM documents WHERE id = ?", (document_id,))
    if not document:
        raise HTTPException(status_code=404, detail="Documentul nu exista.")
    storage_path = Path(document["storage_path"]) if document.get("storage_path") else None
    if not storage_path or not storage_path.is_file():
        raise HTTPException(status_code=404, detail="Fisierul original nu mai este disponibil.")
    return FileResponse(storage_path, media_type=document["mime_type"], filename=document["filename"])


@app.get("/documents/{document_id}")
def get_document(document_id: int) -> dict[str, Any]:
    document = fetch_one(
        """
        SELECT id, filename, kind, mime_type, size, content, analysis_summary, analysis_status,
        analysis_provider, analysis_model, analysis_error, analysis_confidence, created_at
        FROM documents WHERE id = ?
        """,
        (document_id,),
    )
    if not document:
        raise HTTPException(status_code=404, detail="Documentul nu exista.")
    return document


@app.delete("/documents/{document_id}")
def delete_document(document_id: int) -> dict[str, str]:
    document = fetch_one("SELECT id, storage_path FROM documents WHERE id = ?", (document_id,))
    if not document:
        raise HTTPException(status_code=404, detail="Documentul nu exista.")
    storage_path = Path(document["storage_path"]) if document.get("storage_path") else None
    if storage_path and storage_path.is_file():
        storage_path.unlink()
    execute("DELETE FROM analyses WHERE source_document_id = ?", (document_id,))
    execute("DELETE FROM documents WHERE id = ?", (document_id,))
    return {"status": "deleted"}


@app.get("/analyses")
def list_analyses() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM analyses ORDER BY measured_at DESC, created_at DESC")


@app.post("/analyses")
def create_analysis(payload: AnalysisIn) -> dict[str, Any]:
    status = payload.status or classify(payload.name, payload.value)[0]
    item_id = execute(
        """
        INSERT INTO analyses (name, value, unit, reference_range, status, notes, measured_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (payload.name, payload.value, payload.unit, payload.reference_range, status, payload.notes, payload.measured_at, now_iso()),
    )
    return get_analysis(item_id)


@app.post("/analyses/upload")
async def upload_analyses(file: UploadFile = File(...)) -> dict[str, Any]:
    return await upload_document(file, kind="analize")


@app.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int) -> dict[str, Any]:
    item = fetch_one("SELECT * FROM analyses WHERE id = ?", (analysis_id,))
    if not item:
        raise HTTPException(status_code=404, detail="Analiza nu exista.")
    return item


@app.get("/investigations")
def list_investigations() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM investigations ORDER BY performed_at DESC")


@app.post("/investigations")
def create_investigation(payload: InvestigationIn) -> dict[str, Any]:
    item_id = execute(
        "INSERT INTO investigations (title, category, result, status, performed_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (payload.title, payload.category, payload.result, payload.status, payload.performed_at, now_iso()),
    )
    return fetch_one("SELECT * FROM investigations WHERE id = ?", (item_id,))


@app.get("/medications")
def list_medications() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM medications ORDER BY active DESC, name ASC")


@app.post("/medications")
def create_medication(payload: MedicationIn) -> dict[str, Any]:
    item_id = execute(
        """
        INSERT INTO medications (name, dose, frequency, start_date, end_date, instructions, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (payload.name, payload.dose, payload.frequency, payload.start_date, payload.end_date, payload.instructions, int(payload.active), now_iso()),
    )
    return fetch_one("SELECT * FROM medications WHERE id = ?", (item_id,))


@app.patch("/medications/{medication_id}/toggle")
def toggle_medication(medication_id: int) -> dict[str, Any]:
    item = fetch_one("SELECT * FROM medications WHERE id = ?", (medication_id,))
    if not item:
        raise HTTPException(status_code=404, detail="Medicamentul nu exista.")
    execute("UPDATE medications SET active = ? WHERE id = ?", (0 if item["active"] else 1, medication_id))
    return fetch_one("SELECT * FROM medications WHERE id = ?", (medication_id,))


@app.delete("/medications/{medication_id}")
def delete_medication(medication_id: int) -> dict[str, str]:
    execute("DELETE FROM medications WHERE id = ?", (medication_id,))
    return {"status": "deleted"}


@app.get("/history")
def list_history() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM history ORDER BY event_date DESC")


@app.post("/history")
def create_history(payload: HistoryIn) -> dict[str, Any]:
    item_id = execute(
        "INSERT INTO history (title, category, details, event_date, created_at) VALUES (?, ?, ?, ?, ?)",
        (payload.title, payload.category, payload.details, payload.event_date, now_iso()),
    )
    return fetch_one("SELECT * FROM history WHERE id = ?", (item_id,))


@app.get("/monitoring")
def list_monitoring() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM monitoring ORDER BY measured_at DESC")


@app.post("/monitoring")
def create_monitoring(payload: MonitoringIn) -> dict[str, Any]:
    item_id = execute(
        "INSERT INTO monitoring (metric, value, unit, status, measured_at, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (payload.metric, payload.value, payload.unit, payload.status, payload.measured_at, payload.notes, now_iso()),
    )
    return fetch_one("SELECT * FROM monitoring WHERE id = ?", (item_id,))


@app.get("/recommendations")
def list_recommendations() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM recommendations ORDER BY completed ASC, created_at DESC")


@app.post("/recommendations")
def create_recommendation(payload: RecommendationIn) -> dict[str, Any]:
    item_id = execute(
        "INSERT INTO recommendations (title, body, priority, source, created_at) VALUES (?, ?, ?, ?, ?)",
        (payload.title, payload.body, payload.priority, payload.source, now_iso()),
    )
    return fetch_one("SELECT * FROM recommendations WHERE id = ?", (item_id,))


@app.patch("/recommendations/{recommendation_id}/complete")
def complete_recommendation(recommendation_id: int) -> dict[str, Any]:
    if not fetch_one("SELECT id FROM recommendations WHERE id = ?", (recommendation_id,)):
        raise HTTPException(status_code=404, detail="Recomandarea nu exista.")
    execute("UPDATE recommendations SET completed = 1 WHERE id = ?", (recommendation_id,))
    return fetch_one("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,))


@app.get("/appointments")
def list_appointments() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM appointments ORDER BY scheduled_at ASC")


@app.post("/appointments")
def create_appointment(payload: AppointmentIn) -> dict[str, Any]:
    try:
        datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Data programarii nu este valida.") from exc
    item_id = execute(
        "INSERT INTO appointments (doctor, specialty, scheduled_at, location, notes, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (payload.doctor, payload.specialty, payload.scheduled_at, payload.location, payload.notes, payload.status, now_iso()),
    )
    execute(
        "INSERT INTO notifications (title, body, type, created_at) VALUES (?, ?, ?, ?)",
        ("Consultatie programata", f"{payload.specialty} cu {payload.doctor} la {payload.scheduled_at}", "success", now_iso()),
    )
    return fetch_one("SELECT * FROM appointments WHERE id = ?", (item_id,))


@app.delete("/appointments/{appointment_id}")
def delete_appointment(appointment_id: int) -> dict[str, str]:
    execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    return {"status": "deleted"}


@app.get("/notifications")
def list_notifications() -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM notifications ORDER BY read ASC, created_at DESC")


@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int) -> dict[str, Any]:
    execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
    return fetch_one("SELECT * FROM notifications WHERE id = ?", (notification_id,))


@app.get("/settings")
def get_settings() -> dict[str, Any]:
    rows = fetch_all("SELECT key, value FROM settings")
    settings = {row["key"]: row["value"] for row in rows}
    settings["notifications_enabled"] = settings.get("notifications_enabled", "true") == "true"
    return settings


@app.put("/settings")
def update_settings(payload: SettingsIn) -> dict[str, Any]:
    values = payload.model_dump()
    values["notifications_enabled"] = "true" if payload.notifications_enabled else "false"
    for key, value in values.items():
        execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    return get_settings()


@app.get("/quick-questions")
def quick_questions() -> list[str]:
    return [
        "Explica-mi rezultatele pe intelesul meu.",
        "Care sunt valorile care necesita atentie?",
        "Ce intrebari ar trebui sa ii pun medicului?",
        "Genereaza un rezumat medical al dosarului.",
    ]


def build_chat_context() -> str:
    analyses = list_analyses()[:8]
    recommendations = list_recommendations()[:5]
    medications = list_medications()[:8]
    context = {
        "analize": analyses,
        "recomandari": recommendations,
        "medicatie": medications,
        "investigatii": list_investigations()[:5],
        "monitorizare": list_monitoring()[:8],
        "programari": list_appointments()[:5],
    }
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))


@app.post("/chat")
def chat(payload: ChatIn) -> dict[str, Any]:
    analyses = list_analyses()[:8]
    recommendations = list_recommendations()[:5]
    warning = "Nu inlocuiesc medicul. Pentru simptome severe sau urgente, suna la 112."
    if ai_enabled():
        try:
            answer, model, provider = chat_with_ai(payload.message, build_chat_context())
            return {
                "answer": f"{answer}\n\n{warning}",
                "provider": provider,
                "model": model,
                "created_at": now_iso(),
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Chatul AI nu este disponibil momentan. Incearca din nou.") from exc

    lower = payload.message.lower()
    abnormal = [a for a in analyses if a["status"] != "normal"]
    if "atentie" in lower or "valori" in lower:
        body = "Valorile care merita atentie sunt: " + (", ".join(f"{a['name']} {a['value']} {a['unit']}".strip() for a in abnormal) or "nu exista valori marcate in afara intervalului.")
    elif "intrebari" in lower or "medic" in lower:
        body = "Intreaba medicul ce semnificatie au valorile modificate, daca trebuie repetate analizele si ce schimbari sunt recomandate pentru urmatoarele 4-8 saptamani."
    elif "rezumat" in lower:
        body = f"Dosarul contine {table_count('documents')} documente, {table_count('analyses')} analize, {table_count('medications')} medicamente si {table_count('appointments')} programari."
    else:
        body = "Pe baza datelor salvate, pot sumariza analizele, pot pregati intrebari pentru medic si pot evidentia recomandarile deja generate."
    return {
        "answer": f"{body}\n\n{warning}",
        "used_context": {"analyses": analyses, "recommendations": recommendations},
        "created_at": now_iso(),
    }


STATIC_DIR = Path(os.getenv("STATIC_DIR", BASE_DIR / "static"))
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
