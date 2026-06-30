import base64
import html
import io
import re
import zipfile
from typing import Dict, List
from xml.etree import ElementTree

try:
    from analyzer import JOURNAL_PROFILES, _sections, _trim_sentence
except ImportError:  # Allows package imports from unit tests.
    from .analyzer import JOURNAL_PROFILES, _sections, _trim_sentence


WORD_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

JOURNAL_RULES = {
    "BMC Medicine": {
        "abstract": "Structured abstract with Background, Methods, Results, Conclusions.",
        "order": ["Title page", "Abstract", "Keywords", "Background", "Methods", "Results", "Discussion", "Conclusions", "Declarations", "References"],
        "word_target": "Research articles should be concise and include complete declarations.",
    },
    "Journal of Translational Medicine": {
        "abstract": "Structured abstract emphasizing translational relevance.",
        "order": ["Title page", "Abstract", "Keywords", "Introduction", "Methods", "Results", "Discussion", "Translational relevance", "Declarations", "References"],
        "word_target": "Emphasize mechanism, patient relevance, and reproducible methods.",
    },
    "PLOS ONE": {
        "abstract": "Unstructured abstract is acceptable; prioritize methodological clarity.",
        "order": ["Title page", "Abstract", "Introduction", "Methods", "Results", "Discussion", "Data availability", "References"],
        "word_target": "Claims should focus on technical and methodological soundness rather than perceived impact.",
    },
    "Frontiers in Immunology": {
        "abstract": "Concise abstract with immune mechanism and key finding up front.",
        "order": ["Title page", "Abstract", "Introduction", "Materials and methods", "Results", "Discussion", "Conflict of interest", "References"],
        "word_target": "Frame the manuscript for immunology readers with assay and pathway detail.",
    },
}


def convert_docx_to_journal_format(payload: Dict) -> Dict:
    journal = payload.get("journal", "").strip()
    encoded = payload.get("docxBase64", "")
    original_name = payload.get("fileName", "manuscript.docx")

    if not journal:
        raise ValueError("A target journal is required.")
    if not encoded:
        raise ValueError("A .docx file is required.")

    raw_docx = base64.b64decode(encoded)
    text = _extract_docx_text(raw_docx)
    if len(text.strip()) < 100:
        raise ValueError("The uploaded Word document does not contain enough readable text.")

    rules = _journal_rules(journal)
    sections = _sections(text)
    formatted_preview = _format_preview(journal, text, sections, rules)
    warnings = _conversion_warnings(text, sections)
    applied_rules = [
        f"Target journal: {journal}",
        f"Abstract rule: {rules['abstract']}",
        f"Section order: {', '.join(rules['order'])}",
        rules["word_target"],
    ]

    output_docx = _build_docx(formatted_preview)
    safe_journal = re.sub(r"[^A-Za-z0-9]+", "-", journal).strip("-").lower()

    return {
        "journal": journal,
        "fileName": f"{_stem(original_name)}-{safe_journal}-formatted.docx",
        "convertedDocxBase64": base64.b64encode(output_docx).decode("ascii"),
        "formattedPreview": formatted_preview,
        "appliedRules": applied_rules,
        "warnings": warnings,
        "extractedWordCount": len(text.split()),
    }


def _journal_rules(journal: str) -> Dict:
    if journal in JOURNAL_RULES:
        return JOURNAL_RULES[journal]

    known = next((profile for profile in JOURNAL_PROFILES if profile["journal"] == journal), None)
    if known:
        return {
            "abstract": "Use the journal checklist returned by recommendation analysis.",
            "order": ["Title page", "Abstract", "Keywords", "Introduction", "Methods", "Results", "Discussion", "Declarations", "References"],
            "word_target": "; ".join(known["checklist"]),
        }

    return {
        "abstract": "Use a clear biomedical abstract matched to the selected journal instructions.",
        "order": ["Title page", "Abstract", "Keywords", "Introduction", "Methods", "Results", "Discussion", "Declarations", "References"],
        "word_target": "Verify exact author instructions before final submission.",
    }


def _extract_docx_text(raw_docx: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw_docx)) as archive:
        document_xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    paragraphs: List[str] = []
    for paragraph in root.findall(".//w:p", WORD_NS):
        pieces = [node.text or "" for node in paragraph.findall(".//w:t", WORD_NS)]
        text = "".join(pieces).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _format_preview(journal: str, text: str, sections: List[Dict], rules: Dict) -> str:
    title = _first_nonempty_line(text)
    abstract = _extract_named_section(text, "abstract") or _trim_sentence(text, 1200)
    section_map = {section["name"].lower(): section for section in sections}
    order_lines = []

    for section_name in rules["order"]:
        key = section_name.lower().replace("materials and methods", "methods").replace("background", "introduction")
        body = section_map.get(key, {}).get("summary", "")
        if section_name == "Title page":
            body = title
        elif section_name == "Abstract":
            body = _format_abstract(abstract, rules["abstract"])
        elif section_name == "Keywords":
            body = "Add 5-8 MeSH-aligned keywords before submission."
        elif section_name in {"Declarations", "Conflict of interest"}:
            body = "Add ethics approval, consent, funding, competing interests, author contributions, acknowledgements, and data availability statements as required."
        elif section_name == "Data availability":
            body = "Add repository, accession, code, or reasonable-request language before submission."
        elif not body:
            body = "Move or draft this section according to the journal instructions."

        order_lines.append(f"{section_name}\n{body}")

    checklist = "\n".join(f"- {item}" for item in rules.get("word_target", "").split("; ") if item)
    return (
        f"{journal} formatted submission draft\n\n"
        f"Formatting checklist\n{checklist}\n\n"
        + "\n\n".join(order_lines)
    )


def _format_abstract(abstract: str, abstract_rule: str) -> str:
    if "structured" not in abstract_rule.lower():
        return abstract

    return (
        f"Background: {_trim_sentence(abstract, 300)}\n"
        "Methods: Confirm study design, population, endpoint, and statistical methods.\n"
        "Results: Insert the main numerical result and effect estimate.\n"
        "Conclusions: State the interpretation without overclaiming clinical deployment."
    )


def _conversion_warnings(text: str, sections: List[Dict]) -> List[str]:
    present = {section["name"].lower() for section in sections}
    warnings = []
    for required in ["abstract", "methods", "results", "discussion"]:
        if required not in present:
            warnings.append(f"Missing or unrecognized {required.title()} section; placeholder text was inserted.")
    if not re.search(r"(?i)ethics|institutional review|consent|irb", text):
        warnings.append("Ethics/consent language was not detected.")
    if not re.search(r"(?i)data availability|code availability|repository|accession", text):
        warnings.append("Data or code availability language was not detected.")
    return warnings or ["No major structural warnings detected by the local formatter."]


def _build_docx(text: str) -> bytes:
    paragraphs = text.split("\n")
    body = "\n".join(_paragraph_xml(paragraph) for paragraph in paragraphs)
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{WORD_NS['w']}" xmlns:r="{WORD_NS['r']}">
  <w:body>
    {body}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def _paragraph_xml(text: str) -> str:
    escaped = html.escape(text)
    if not escaped:
        return "<w:p/>"
    return f"<w:p><w:r><w:t>{escaped}</w:t></w:r></w:p>"


def _extract_named_section(text: str, name: str) -> str:
    match = re.search(
        rf"(?is){name}:\s*(.+?)(?:\n\s*(?:introduction|methods|results|discussion|limitations|conclusion|references):|$)",
        text,
    )
    return match.group(1).strip() if match else ""


def _first_nonempty_line(text: str) -> str:
    return next((line.strip().replace("Title:", "").strip() for line in text.splitlines() if line.strip()), "Untitled manuscript")


def _stem(file_name: str) -> str:
    return re.sub(r"\.docx$", "", file_name, flags=re.IGNORECASE) or "manuscript"
