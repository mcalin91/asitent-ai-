import base64
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedAnalysis(BaseModel):
    name: str = Field(min_length=1)
    value: float
    unit: str = ""
    reference_range: str = ""
    status: Literal["normal", "crescut", "scazut", "atentie", "necunoscut"] = "necunoscut"
    notes: str = ""
    measured_at: str | None = None


class MedicalDocumentResult(BaseModel):
    document_type: str = "document medical"
    document_date: str | None = None
    extracted_text: str = ""
    summary: str = Field(min_length=1)
    analyses: list[ExtractedAnalysis] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)


@dataclass
class AIServiceResult:
    result: MedicalDocumentResult
    provider: str
    model: str


SYSTEM_PROMPT = """
Esti un extractor de date din documente medicale in limba romana sau engleza.
Transcrie fidel textul medical lizibil si returneaza numai date sustinute de document.
Nu inventa valori, unitati, intervale, diagnostice sau recomandari.

Pentru fiecare analiza numerica:
- copiaza numele, valoarea, unitatea si intervalul de referinta exact cum apar;
- stabileste statusul numai daca intervalul din document permite asta;
- foloseste "necunoscut" daca nu exista suficiente informatii.

Rezumatul trebuie sa fie scurt, factual si usor de inteles. Alertele descriu doar
valori marcate de laborator sau clar in afara intervalului tiparit. Recomandarile
trebuie formulate ca subiecte de discutat cu medicul, nu ca diagnostic ori tratament.
Nu include date personale inutile. Pentru urgente mentioneaza evaluarea medicala
imediata, fara a pretinde ca documentul confirma o urgenta.
""".strip()


def ai_enabled() -> bool:
    provider = configured_provider()
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY", "").strip())
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def configured_model() -> str:
    if configured_provider() == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    return os.getenv("OPENAI_MODEL", "gpt-5.6-sol")


def configured_provider() -> str:
    provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
    return provider if provider in {"gemini", "openai"} else "gemini"


def _data_url(raw: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def extract_local_text(raw: bytes, filename: str, mime_type: str) -> str:
    suffix = Path(filename).suffix.lower()
    if mime_type == "application/pdf" or suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw))
            return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
        except Exception:
            return ""

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or suffix == ".docx":
        try:
            from docx import Document

            document = Document(io.BytesIO(raw))
            return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
        except Exception:
            return ""

    if mime_type.startswith("text/") or suffix in {".txt", ".csv", ".md"}:
        for encoding in ("utf-8", "cp1250", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
    return ""


def analyze_with_openai(raw: bytes, filename: str, mime_type: str, local_text: str = "") -> AIServiceResult:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY nu este configurata.")

    from openai import OpenAI

    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": (
                f"Analizeaza documentul {Path(filename).name}. "
                "Returneaza toate valorile medicale numerice lizibile si textul medical relevant."
            ),
        }
    ]
    if mime_type.startswith("image/"):
        content.append({"type": "input_image", "image_url": _data_url(raw, mime_type), "detail": "high"})
    elif mime_type == "application/pdf" or Path(filename).suffix.lower() == ".pdf":
        content.append(
            {
                "type": "input_file",
                "filename": Path(filename).name,
                "file_data": _data_url(raw, "application/pdf"),
            }
        )
    elif local_text:
        content.append({"type": "input_text", "text": f"Continut extras local:\n{local_text[:120_000]}"})
    else:
        raise ValueError("Tipul de fisier nu poate fi analizat.")

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
    response = client.responses.parse(
        model=model,
        reasoning={"effort": os.getenv("OPENAI_REASONING_EFFORT", "low")},
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        text_format=MedicalDocumentResult,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("Modelul nu a returnat un rezultat medical valid.")
    return AIServiceResult(result=parsed, provider="openai", model=model)


def chat_with_openai(message: str, context: str) -> tuple[str, str]:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY nu este configurata.")

    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
    response = client.responses.create(
        model=model,
        reasoning={"effort": os.getenv("OPENAI_REASONING_EFFORT", "low")},
        store=False,
        input=[
            {
                "role": "system",
                "content": (
                    "Esti un asistent pentru intelegerea unui dosar medical personal. "
                    "Raspunde in romana, clar si prudent, numai din contextul furnizat. "
                    "Nu pune diagnostic, nu prescrie si nu modifica tratamente. Spune clar "
                    "cand informatia lipseste. Pentru simptome severe recomanda 112."
                ),
            },
            {"role": "user", "content": f"CONTEXT DOSAR:\n{context}\n\nINTREBARE:\n{message}"},
        ],
    )
    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("Modelul nu a returnat un raspuns.")
    return answer, model


def analyze_with_gemini(raw: bytes, filename: str, mime_type: str, local_text: str = "") -> AIServiceResult:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nu este configurata.")

    from google import genai

    prompt = (
        f"{SYSTEM_PROMPT}\n\nAnalizeaza documentul {Path(filename).name}. "
        "Returneaza toate valorile medicale numerice lizibile si textul medical relevant."
    )
    content: list[dict[str, str]] = []
    encoded = base64.b64encode(raw).decode("ascii")
    if mime_type.startswith("image/"):
        content.append({"type": "image", "data": encoded, "mime_type": mime_type})
    elif mime_type == "application/pdf" or Path(filename).suffix.lower() == ".pdf":
        content.append({"type": "document", "data": encoded, "mime_type": "application/pdf"})
    elif local_text:
        prompt = f"{prompt}\n\nContinut extras local:\n{local_text[:120_000]}"
    else:
        raise ValueError("Tipul de fisier nu poate fi analizat.")
    content.append({"type": "text", "text": prompt})

    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=model,
        store=False,
        input=content,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": MedicalDocumentResult.model_json_schema(),
        },
    )
    if not interaction.output_text:
        raise RuntimeError("Gemini nu a returnat un rezultat medical valid.")
    parsed = MedicalDocumentResult.model_validate_json(interaction.output_text)
    return AIServiceResult(result=parsed, provider="gemini", model=model)


def chat_with_gemini(message: str, context: str) -> tuple[str, str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nu este configurata.")

    from google import genai

    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=model,
        store=False,
        input=(
            "Esti un asistent pentru intelegerea unui dosar medical personal. "
            "Raspunde in romana, clar si prudent, numai din contextul furnizat. "
            "Nu pune diagnostic, nu prescrie si nu modifica tratamente. Spune clar "
            "cand informatia lipseste. Pentru simptome severe recomanda 112.\n\n"
            f"CONTEXT DOSAR:\n{context}\n\nINTREBARE:\n{message}"
        ),
    )
    answer = (interaction.output_text or "").strip()
    if not answer:
        raise RuntimeError("Gemini nu a returnat un raspuns.")
    return answer, model


def analyze_with_ai(raw: bytes, filename: str, mime_type: str, local_text: str = "") -> AIServiceResult:
    if configured_provider() == "gemini":
        return analyze_with_gemini(raw, filename, mime_type, local_text)
    return analyze_with_openai(raw, filename, mime_type, local_text)


def chat_with_ai(message: str, context: str) -> tuple[str, str, str]:
    provider = configured_provider()
    if provider == "gemini":
        answer, model = chat_with_gemini(message, context)
    else:
        answer, model = chat_with_openai(message, context)
    return answer, model, provider
