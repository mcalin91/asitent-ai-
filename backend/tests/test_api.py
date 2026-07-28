import importlib
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


def make_client(tmp_path: Path) -> TestClient:
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.sqlite3")
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ["AI_PROVIDER"] = "gemini"
    import app.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_dashboard_and_inventory(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.get("/health").json()["status"] == "ok"
    inventory = client.get("/inventory").json()
    assert "Dashboard" in inventory["screens"]
    assert "Chat AI" in inventory["actions"]
    dashboard = client.get("/dashboard").json()
    assert "stats" in dashboard
    assert "recent_documents" in dashboard
    ai_status = client.get("/ai/status").json()
    assert ai_status["enabled"] is False
    assert ai_status["ocr"] is False
    doctor_status = client.get("/doctors/status").json()
    assert doctor_status["enabled"] is False


def test_upload_document_extracts_analyses_and_chat(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    content = b"Glicemie 126 mg/dL\nHbA1c 6.1 %\nVitamina D 18 ng/mL\nTSH 2.1"
    response = client.post("/documents", files={"file": ("analize.txt", content, "text/plain")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["analyses"]) >= 4
    analyses = client.get("/analyses").json()
    assert any(item["status"] != "normal" for item in analyses)
    chat = client.post("/chat", json={"message": "Care sunt valorile care necesita atentie?"}).json()
    assert "Nu inlocuiesc medicul" in chat["answer"]


def test_create_core_records_and_export(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert client.post("/medications", json={"name": "Metformin", "dose": "500 mg", "frequency": "seara"}).status_code == 200
    assert client.post("/appointments", json={"doctor": "Dr. Popescu", "specialty": "Diabetologie", "scheduled_at": "2026-08-10T09:00:00"}).status_code == 200
    assert client.post("/monitoring", json={"metric": "Puls", "value": 72, "unit": "bpm"}).status_code == 200
    exported = client.get("/medical-record/export")
    assert exported.status_code == 200
    data = exported.json()
    assert data["medications"]
    assert data["appointments"]


def test_scanned_document_requires_ai_key(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/documents", files={"file": ("scan.png", b"not-a-real-image", "image/png")})
    assert response.status_code == 503
    documents = client.get("/documents").json()
    assert documents[0]["analysis_status"] == "needs_ai"


def test_rejects_unsupported_upload_type(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/documents", files={"file": ("archive.zip", b"content", "application/zip")})
    assert response.status_code == 415


def test_ai_document_result_is_persisted(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    import app.main as main
    from app.ai_service import AIServiceResult, ExtractedAnalysis, MedicalDocumentResult

    monkeypatch.setattr(main, "ai_enabled", lambda: True)
    monkeypatch.setattr(
        main,
        "analyze_with_ai",
        lambda *args: AIServiceResult(
            result=MedicalDocumentResult(
                document_type="buletin analize",
                extracted_text="Glicemie 126 mg/dL",
                summary="A fost extrasa o valoare.",
                analyses=[
                    ExtractedAnalysis(
                        name="Glicemie",
                        value=126,
                        unit="mg/dL",
                        reference_range="70-99",
                        status="crescut",
                    )
                ],
                alerts=["Glicemia este peste intervalul tiparit."],
                recommendations=["Discuta valoarea glicemiei cu medicul."],
                confidence=0.94,
            ),
            provider="gemini",
            model="test-model",
        ),
    )
    response = client.post("/documents", files={"file": ("scan.png", b"fake-image", "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "gemini"
    assert body["analyses"][0]["status"] == "crescut"
    document = client.get("/documents").json()[0]
    assert document["analysis_status"] == "completed"
    assert document["analysis_confidence"] == 0.94
    downloaded = client.get(f"/documents/{body['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == b"fake-image"


def test_doctor_specialty_recommendation_and_search_contract(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    import app.main as main

    client.post(
        "/analyses",
        json={"name": "Glicemie", "value": 126, "unit": "mg/dL", "status": "crescut"},
    )
    without_key = client.get("/doctors/recommendations?latitude=44.4268&longitude=26.1025&radius_km=10")
    assert without_key.status_code == 503

    monkeypatch.setattr(main, "places_enabled", lambda: True)
    monkeypatch.setattr(
        main,
        "search_doctors",
        lambda latitude, longitude, radius_km, specialties: [
            {
                "place_id": "place-test",
                "name": "Clinica Test",
                "address": "Bucuresti",
                "rating": 4.8,
                "review_count": 120,
                "distance_km": 2.1,
                "matched_specialties": specialties,
                "reviews": [],
            }
        ],
    )
    response = client.get("/doctors/recommendations?latitude=44.4268&longitude=26.1025&radius_km=10")
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_specialties"][0]["specialty"] == "Diabetologie"
    assert body["doctors"][0]["name"] == "Clinica Test"


def test_gemini_structured_image_request(monkeypatch) -> None:
    from google import genai
    from app.ai_service import analyze_with_gemini

    captured = {}

    class FakeInteractions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return type(
                "Interaction",
                (),
                {
                    "output_text": json.dumps(
                        {
                            "document_type": "buletin analize",
                            "document_date": None,
                            "extracted_text": "Glicemie 126 mg/dL",
                            "summary": "O valoare extrasa.",
                            "analyses": [
                                {
                                    "name": "Glicemie",
                                    "value": 126,
                                    "unit": "mg/dL",
                                    "reference_range": "70-99",
                                    "status": "crescut",
                                    "notes": "",
                                    "measured_at": None,
                                }
                            ],
                            "alerts": [],
                            "recommendations": [],
                            "confidence": 0.95,
                        }
                    )
                },
            )()

    class FakeClient:
        def __init__(self, **kwargs):
            self.interactions = FakeInteractions()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setattr(genai, "Client", FakeClient)
    result = analyze_with_gemini(b"image-bytes", "analize.png", "image/png")

    assert result.provider == "gemini"
    assert result.result.analyses[0].value == 126
    assert captured["model"] == "gemini-test"
    assert captured["store"] is False
    assert captured["input"][0]["type"] == "image"
    assert captured["response_format"]["mime_type"] == "application/json"
