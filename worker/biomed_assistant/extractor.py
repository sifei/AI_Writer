import base64
import re
from typing import Dict

try:
    from converter import _extract_docx_text
except ImportError:  # Allows package imports from unit tests.
    from .converter import _extract_docx_text


def extract_uploaded_text(payload: Dict) -> Dict:
    file_name = payload.get("fileName", "manuscript").strip()
    encoded = payload.get("fileBase64", "")
    mime_type = payload.get("mimeType", "")

    if not encoded:
        raise ValueError("Upload a .docx, .txt, or .tex file first.")

    raw = base64.b64decode(encoded)
    detected_type = _detect_type(file_name, mime_type)

    if detected_type == "docx":
        text = _extract_docx_text(raw)
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        if detected_type == "latex":
            text = _clean_latex(text)

    text = _normalize_text(text)
    if len(text) < 100:
        raise ValueError("The uploaded file does not contain enough readable manuscript text.")

    return {
        "fileName": file_name,
        "detectedType": detected_type,
        "text": text,
        "wordCount": len(text.split()),
        "warnings": _warnings(text, detected_type),
    }


def _detect_type(file_name: str, mime_type: str) -> str:
    lowered = file_name.lower()
    if lowered.endswith(".docx") or "wordprocessingml" in mime_type:
        return "docx"
    if lowered.endswith(".tex") or lowered.endswith(".latex"):
        return "latex"
    if lowered.endswith(".txt") or mime_type.startswith("text/") or not mime_type:
        return "txt"
    raise ValueError("Unsupported file type. Please upload .docx, .txt, or .tex.")


def _clean_latex(text: str) -> str:
    text = re.sub(r"(?s)%.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\\(?:title|section|subsection|subsubsection)\*?\{([^{}]*)\}", r"\1:\n", text)
    text = re.sub(r"\\begin\{abstract\}", "Abstract:\n", text)
    text = re.sub(r"\\end\{abstract\}", "\n", text)
    text = re.sub(r"\\(?:textbf|textit|emph)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\cite\{[^{}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", text)
    text = re.sub(r"[{}$]", " ", text)
    return text


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _warnings(text: str, detected_type: str):
    warnings = [f"Detected {detected_type.upper()} upload and extracted text for journal matching."]
    if detected_type == "latex":
        warnings.append("LaTeX commands were simplified; verify equations, tables, and citations manually.")
    if not re.search(r"(?i)\babstract\b", text):
        warnings.append("No explicit Abstract heading was detected.")
    return warnings
