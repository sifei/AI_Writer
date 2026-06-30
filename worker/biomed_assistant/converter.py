import base64
import html
import io
import re
import zipfile
from typing import Dict, List, Tuple
from xml.etree import ElementTree

try:
    from analyzer import JOURNAL_PROFILES, _trim_sentence
except ImportError:  # Allows package imports from unit tests.
    from .analyzer import JOURNAL_PROFILES, _trim_sentence


WORD_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16": "http://schemas.microsoft.com/office/word/2018/wordml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
}

for prefix, uri in WORD_NS.items():
    ElementTree.register_namespace(prefix, uri)

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

    rules = _formatting_rules(journal)
    sections = _full_sections(text)
    formatted_preview = _format_preview(journal, text, sections, rules["text_rules"])
    output_docx, structure = _format_existing_docx(raw_docx, text, rules)
    warnings = _conversion_warnings(text, sections, structure, rules)
    applied_rules = [
        f"Target journal: {journal}",
        f"Layout mode: {rules['layout_mode']}",
        f"Body font: {rules['font_family']} {rules['font_size_pt']} pt",
        f"Line spacing: {rules['line_spacing']}",
        f"Columns: {rules['columns']}",
        f"Abstract rule: {rules['text_rules']['abstract']}",
        f"Section order: {', '.join(rules['text_rules']['order'])}",
        rules["text_rules"]["word_target"],
    ]
    safe_journal = re.sub(r"[^A-Za-z0-9]+", "-", journal).strip("-").lower()
    caption_warnings = _caption_warnings(text, structure)

    return {
        "journal": journal,
        "fileName": f"{_stem(original_name)}-{safe_journal}-formatted.docx",
        "convertedDocxBase64": base64.b64encode(output_docx).decode("ascii"),
        "formattedPreview": formatted_preview,
        "appliedRules": applied_rules,
        "warnings": warnings,
        "extractedWordCount": len(text.split()),
        "tableCount": structure["table_count"],
        "figureCount": structure["figure_count"],
        "captionWarnings": caption_warnings,
        "layoutMode": rules["layout_mode"],
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


def _formatting_rules(journal: str) -> Dict:
    text_rules = _journal_rules(journal)
    normalized = journal.lower()
    rules = {
        "journal": journal,
        "text_rules": text_rules,
        "layout_mode": "single-column submission manuscript",
        "columns": 1,
        "font_family": "Times New Roman",
        "font_size_pt": 12,
        "line_spacing": "double",
        "line_spacing_twips": "480",
        "paragraph_after_twips": "120",
        "top_margin": "1440",
        "right_margin": "1440",
        "bottom_margin": "1440",
        "left_margin": "1440",
        "max_image_cx": 5486400,
        "line_numbers": False,
        "required_sections": ["Data availability", "Funding", "Competing interests"],
    }

    if "ieee access" in normalized:
        rules.update(
            {
                "layout_mode": "IEEE two-column technical layout",
                "columns": 2,
                "font_family": "Times New Roman",
                "font_size_pt": 10,
                "line_spacing": "single",
                "line_spacing_twips": "240",
                "paragraph_after_twips": "80",
                "top_margin": "720",
                "right_margin": "720",
                "bottom_margin": "720",
                "left_margin": "720",
                "required_sections": ["Index Terms", "Data availability", "Acknowledgment"],
            }
        )
    elif "jamia" in normalized or "american medical informatics" in normalized:
        rules.update(
            {
                "line_spacing": "double",
                "required_sections": ["Background and Significance", "Funding", "Competing interests", "Author contributions"],
            }
        )
    elif "biomedical informatics" in normalized:
        rules.update(
            {
                "line_spacing": "double",
                "required_sections": ["Declarations", "Data availability", "Competing interests"],
            }
        )
    elif "npj digital medicine" in normalized:
        rules.update(
            {
                "line_spacing": "single",
                "line_spacing_twips": "300",
                "required_sections": ["Data availability", "Code availability", "Author contributions", "Competing interests"],
            }
        )
    elif "plos one" in normalized:
        rules.update(
            {
                "line_spacing": "double",
                "line_numbers": True,
                "required_sections": ["Data availability", "Funding", "Competing interests"],
            }
        )

    return rules


def _format_existing_docx(raw_docx: bytes, text: str, rules: Dict) -> Tuple[bytes, Dict]:
    with zipfile.ZipFile(io.BytesIO(raw_docx)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}

    root = ElementTree.fromstring(entries["word/document.xml"])
    structure = _document_structure(entries, root)
    structure["inserted_sections"] = _ensure_required_sections(root, text, rules["required_sections"])

    _apply_page_layout(root, rules)
    _style_paragraphs(root, rules)
    _style_tables(root)
    _style_figures(root, rules)
    _strip_markup_compatibility_ignorable(root)

    entries["word/document.xml"] = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue(), structure


def _document_structure(entries: Dict[str, bytes], root: ElementTree.Element) -> Dict:
    media_count = len([name for name in entries if name.startswith("word/media/")])
    drawing_count = len(root.findall(".//w:drawing", WORD_NS))
    return {
        "table_count": len(root.findall(".//w:tbl", WORD_NS)),
        "figure_count": max(media_count, drawing_count),
        "media_count": media_count,
        "drawing_count": drawing_count,
    }


def _apply_page_layout(root: ElementTree.Element, rules: Dict) -> None:
    body = root.find("w:body", WORD_NS)
    if body is None:
        return
    section_properties = root.findall(".//w:sectPr", WORD_NS)
    body_sect_pr = body.find("w:sectPr", WORD_NS)
    if body_sect_pr is None:
        body_sect_pr = ElementTree.SubElement(body, _qn("w:sectPr"))
        section_properties.append(body_sect_pr)

    for sect_pr in section_properties:
        _apply_section_layout(sect_pr, rules)


def _apply_section_layout(sect_pr: ElementTree.Element, rules: Dict) -> None:
    pg_sz = _ensure_child(sect_pr, "w:pgSz")
    pg_sz.set(_qn("w:w"), "12240")
    pg_sz.set(_qn("w:h"), "15840")

    pg_mar = _ensure_child(sect_pr, "w:pgMar")
    pg_mar.set(_qn("w:top"), rules["top_margin"])
    pg_mar.set(_qn("w:right"), rules["right_margin"])
    pg_mar.set(_qn("w:bottom"), rules["bottom_margin"])
    pg_mar.set(_qn("w:left"), rules["left_margin"])
    pg_mar.set(_qn("w:header"), "720")
    pg_mar.set(_qn("w:footer"), "720")
    pg_mar.set(_qn("w:gutter"), "0")

    cols = _ensure_child(sect_pr, "w:cols")
    cols.set(_qn("w:num"), str(rules["columns"]))
    if rules["columns"] == 2:
        cols.set(_qn("w:space"), "720")
    elif _qn("w:space") in cols.attrib:
        del cols.attrib[_qn("w:space")]

    existing_line_numbers = sect_pr.find("w:lnNumType", WORD_NS)
    if rules.get("line_numbers"):
        line_numbers = _ensure_child(sect_pr, "w:lnNumType")
        line_numbers.set(_qn("w:countBy"), "1")
    elif existing_line_numbers is not None:
        sect_pr.remove(existing_line_numbers)


def _style_paragraphs(root: ElementTree.Element, rules: Dict) -> None:
    for index, paragraph in enumerate(root.findall(".//w:p", WORD_NS)):
        text = _paragraph_text(paragraph)
        if not text:
            continue

        p_pr = _ensure_first_child(paragraph, "w:pPr")
        spacing = _ensure_child(p_pr, "w:spacing")
        spacing.set(_qn("w:line"), rules["line_spacing_twips"])
        spacing.set(_qn("w:lineRule"), "auto")
        spacing.set(_qn("w:after"), rules["paragraph_after_twips"])

        if _looks_like_heading(text):
            _set_paragraph_run_format(paragraph, rules["font_family"], 14, bold=True)
        elif _looks_like_caption(text):
            _set_paragraph_run_format(paragraph, rules["font_family"], max(9, rules["font_size_pt"] - 1), italic=True)
        elif index == 0 or text.lower().startswith("title:"):
            _set_paragraph_run_format(paragraph, rules["font_family"], 14, bold=True)
            jc = _ensure_child(p_pr, "w:jc")
            jc.set(_qn("w:val"), "center")
        else:
            _set_paragraph_run_format(paragraph, rules["font_family"], rules["font_size_pt"])


def _style_tables(root: ElementTree.Element) -> None:
    for table in root.findall(".//w:tbl", WORD_NS):
        tbl_pr = _ensure_first_child(table, "w:tblPr")
        tbl_w = _ensure_child(tbl_pr, "w:tblW")
        tbl_w.set(_qn("w:w"), "5000")
        tbl_w.set(_qn("w:type"), "pct")

        borders = _ensure_child(tbl_pr, "w:tblBorders")
        for border_name in ["top", "left", "bottom", "right", "insideH", "insideV"]:
            border = _ensure_child(borders, f"w:{border_name}")
            border.set(_qn("w:val"), "single")
            border.set(_qn("w:sz"), "4")
            border.set(_qn("w:space"), "0")
            border.set(_qn("w:color"), "B7C4BD")

        margins = _ensure_child(tbl_pr, "w:tblCellMar")
        for side in ["top", "left", "bottom", "right"]:
            margin = _ensure_child(margins, f"w:{side}")
            margin.set(_qn("w:w"), "120")
            margin.set(_qn("w:type"), "dxa")

        rows = table.findall("w:tr", WORD_NS)
        if rows:
            tr_pr = _ensure_first_child(rows[0], "w:trPr")
            header = _ensure_child(tr_pr, "w:tblHeader")
            header.set(_qn("w:val"), "true")


def _style_figures(root: ElementTree.Element, rules: Dict) -> None:
    max_cx = rules["max_image_cx"]
    for extent in root.findall(".//wp:extent", WORD_NS):
        try:
            cx = int(extent.get("cx", "0"))
            cy = int(extent.get("cy", "0"))
        except ValueError:
            continue
        if cx > max_cx and cx > 0:
            ratio = max_cx / cx
            extent.set("cx", str(max_cx))
            extent.set("cy", str(max(1, int(cy * ratio))))


def _ensure_required_sections(root: ElementTree.Element, text: str, required_sections: List[str]) -> List[str]:
    body = root.find("w:body", WORD_NS)
    if body is None:
        return []

    sect_pr = body.find("w:sectPr", WORD_NS)
    insert_index = list(body).index(sect_pr) if sect_pr is not None else len(list(body))
    inserted = []
    lowered = text.lower()

    for section in required_sections:
        if section.lower() in lowered:
            continue
        heading = _new_paragraph(section, bold=True)
        placeholder = _new_paragraph(f"Add {section.lower()} statement required by the selected journal before submission.")
        body.insert(insert_index, heading)
        body.insert(insert_index + 1, placeholder)
        insert_index += 2
        inserted.append(section)

    return inserted


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
    abstract = _extract_named_section(text, "abstract") or _trim_sentence(text, 2500)
    section_map = {_section_key(section["name"]): section["body"] for section in sections}
    consumed_keys = set()
    order_lines = []

    for section_name in rules["order"]:
        key = _section_key(section_name)
        body = section_map.get(key, "")
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
        else:
            consumed_keys.add(key)

        order_lines.append(f"{section_name}\n{body}")

    remaining_sections = [
        f"{section['name']}\n{section['body']}"
        for section in sections
        if _section_key(section["name"]) not in consumed_keys
        and _section_key(section["name"]) not in {"title", "abstract"}
    ]

    if not sections or (len(sections) == 1 and sections[0]["name"] == "Manuscript"):
        remaining_sections = [f"Manuscript body\n{_strip_title_and_abstract(text)}"]

    checklist = "\n".join(f"- {item}" for item in rules.get("word_target", "").split("; ") if item)
    return (
        f"{journal} formatted submission draft\n\n"
        f"Formatting checklist\n{checklist}\n\n"
        + "\n\n".join(order_lines + remaining_sections)
    )


def _format_abstract(abstract: str, abstract_rule: str) -> str:
    if "structured" not in abstract_rule.lower():
        return abstract

    if re.search(r"(?i)\b(background|methods|results|conclusions?)\s*:", abstract):
        return abstract

    return (
        f"Background: {abstract}\n"
        "Methods: Confirm study design, population, endpoint, and statistical methods in this subsection.\n"
        "Results: Move the main numerical result and effect estimate here if they are currently embedded above.\n"
        "Conclusions: State the interpretation without overclaiming clinical deployment."
    )


def _conversion_warnings(text: str, sections: List[Dict], structure: Dict, rules: Dict) -> List[str]:
    present = {section["name"].lower() for section in sections}
    warnings = []
    for required in ["abstract", "methods", "results", "discussion"]:
        if required not in present:
            warnings.append(f"Missing or unrecognized {required.title()} section; placeholder text was inserted.")
    if not re.search(r"(?i)ethics|institutional review|consent|irb", text):
        warnings.append("Ethics/consent language was not detected.")
    if not re.search(r"(?i)data availability|code availability|repository|accession", text):
        warnings.append("Data or code availability language was not detected.")
    for inserted in structure.get("inserted_sections", []):
        warnings.append(f"Added placeholder for missing required section: {inserted}.")
    if structure["table_count"]:
        warnings.append(f"Detected and preserved {structure['table_count']} table(s); verify column widths after download.")
    if structure["figure_count"]:
        warnings.append(f"Detected and preserved {structure['figure_count']} figure/media item(s); verify captions and image placement after download.")
    if rules["columns"] == 2:
        warnings.append("Applied two-column IEEE-style layout; verify this is appropriate for the selected submission stage.")
    return warnings or ["No major structural warnings detected by the local formatter."]


def _caption_warnings(text: str, structure: Dict) -> List[str]:
    warnings = []
    figure_caption_count = len(re.findall(r"(?im)^\s*(figure|fig\.?)\s*\d+", text))
    table_caption_count = len(re.findall(r"(?im)^\s*table\s*\d+", text))
    if structure["figure_count"] and figure_caption_count < structure["figure_count"]:
        warnings.append("Some figures may be missing captions or standard Figure numbering.")
    if structure["table_count"] and table_caption_count < structure["table_count"]:
        warnings.append("Some tables may be missing captions or standard Table numbering.")
    return warnings


def _full_sections(text: str) -> List[Dict]:
    pattern = re.compile(
        r"(?ims)^\s*(title|abstract|introduction|background|methods|materials and methods|results|discussion|limitations|conclusions?|references|acknowledgements?|funding|data availability|ethics|declarations):?\s*(.*?)(?=^\s*(?:title|abstract|introduction|background|methods|materials and methods|results|discussion|limitations|conclusions?|references|acknowledgements?|funding|data availability|ethics|declarations):?\s*|\Z)"
    )
    sections = []
    for name, body in pattern.findall(text):
        normalized_name = name.strip().title()
        if normalized_name == "Materials And Methods":
            normalized_name = "Methods"
        if normalized_name == "Conclusion":
            normalized_name = "Conclusions"
        clean_body = _clean_section_body(body)
        if clean_body:
            sections.append(
                {
                    "name": normalized_name,
                    "body": clean_body,
                    "wordCount": len(clean_body.split()),
                }
            )

    if sections:
        return sections

    return [
        {
            "name": "Manuscript",
            "body": _clean_section_body(text),
            "wordCount": len(text.split()),
        }
    ]


def _section_key(name: str) -> str:
    lowered = name.strip().lower()
    aliases = {
        "materials and methods": "methods",
        "background": "introduction",
        "conclusion": "conclusions",
    }
    return aliases.get(lowered, lowered)


def _clean_section_body(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def _strip_title_and_abstract(text: str) -> str:
    without_title = re.sub(r"(?im)^\s*title:\s*.+$", "", text).strip()
    return _clean_section_body(without_title)


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


def _qn(tag: str) -> str:
    prefix, local = tag.split(":", 1)
    return f"{{{WORD_NS[prefix]}}}{local}"


def _ensure_child(parent: ElementTree.Element, tag: str) -> ElementTree.Element:
    child = parent.find(tag, WORD_NS)
    if child is None:
        child = ElementTree.SubElement(parent, _qn(tag))
    return child


def _ensure_first_child(parent: ElementTree.Element, tag: str) -> ElementTree.Element:
    child = parent.find(tag, WORD_NS)
    if child is not None:
        return child
    child = ElementTree.Element(_qn(tag))
    parent.insert(0, child)
    return child


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", WORD_NS)).strip()


def _looks_like_heading(text: str) -> bool:
    normalized = text.strip().lower().rstrip(":")
    headings = {
        "abstract",
        "keywords",
        "index terms",
        "introduction",
        "background",
        "background and significance",
        "objective",
        "methods",
        "materials and methods",
        "results",
        "discussion",
        "conclusion",
        "conclusions",
        "data availability",
        "code availability",
        "author contributions",
        "competing interests",
        "funding",
        "declarations",
        "references",
        "acknowledgments",
        "acknowledgements",
    }
    return normalized in headings or bool(re.match(r"^\d+(\.\d+)*\s+[A-Z][A-Za-z ]{2,60}$", text.strip()))


def _looks_like_caption(text: str) -> bool:
    return bool(re.match(r"(?i)^\s*(figure|fig\.?|table)\s*\d+", text))


def _set_paragraph_style(p_pr: ElementTree.Element, style_id: str) -> None:
    style = _ensure_child(p_pr, "w:pStyle")
    style.set(_qn("w:val"), style_id)


def _set_paragraph_run_format(
    paragraph: ElementTree.Element,
    font_family: str,
    font_size_pt: int,
    bold: bool = False,
    italic: bool = False,
) -> None:
    runs = paragraph.findall("w:r", WORD_NS)
    if not runs:
        return
    for run in runs:
        r_pr = _ensure_first_child(run, "w:rPr")
        fonts = _ensure_child(r_pr, "w:rFonts")
        fonts.set(_qn("w:ascii"), font_family)
        fonts.set(_qn("w:hAnsi"), font_family)
        size = _ensure_child(r_pr, "w:sz")
        size.set(_qn("w:val"), str(font_size_pt * 2))

        _set_toggle(r_pr, "w:b", bold)
        _set_toggle(r_pr, "w:i", italic)


def _set_toggle(parent: ElementTree.Element, tag: str, enabled: bool) -> None:
    existing = parent.find(tag, WORD_NS)
    if enabled:
        node = _ensure_child(parent, tag)
        node.set(_qn("w:val"), "true")
    elif existing is not None:
        parent.remove(existing)


def _new_paragraph(text: str, bold: bool = False) -> ElementTree.Element:
    paragraph = ElementTree.Element(_qn("w:p"))
    p_pr = ElementTree.SubElement(paragraph, _qn("w:pPr"))
    spacing = ElementTree.SubElement(p_pr, _qn("w:spacing"))
    spacing.set(_qn("w:after"), "120")
    run = ElementTree.SubElement(paragraph, _qn("w:r"))
    r_pr = ElementTree.SubElement(run, _qn("w:rPr"))
    fonts = ElementTree.SubElement(r_pr, _qn("w:rFonts"))
    fonts.set(_qn("w:ascii"), "Times New Roman")
    fonts.set(_qn("w:hAnsi"), "Times New Roman")
    size = ElementTree.SubElement(r_pr, _qn("w:sz"))
    size.set(_qn("w:val"), "24")
    if bold:
        ElementTree.SubElement(r_pr, _qn("w:b")).set(_qn("w:val"), "true")
    text_node = ElementTree.SubElement(run, _qn("w:t"))
    text_node.text = text
    return paragraph


def _strip_markup_compatibility_ignorable(root: ElementTree.Element) -> None:
    for element in root.iter():
        for attr in list(element.attrib):
            if attr == _qn("mc:Ignorable") or attr.endswith("}Ignorable"):
                del element.attrib[attr]


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
