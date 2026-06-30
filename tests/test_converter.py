import base64
import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker.biomed_assistant.converter import _build_docx, _extract_docx_text, convert_docx_to_journal_format


TEXT = """
Title: Immune signatures and checkpoint inhibitor response in melanoma

Abstract: We conducted a prospective cohort study of adults with metastatic melanoma receiving checkpoint inhibition.

Methods: Adults were enrolled across three academic centers. Institutional review board approval and consent were obtained.

Results: Durable response was associated with lower IL-8 and preserved tryptophan metabolism.

Discussion: External validation is needed before clinical deployment.
"""


class ConverterTests(unittest.TestCase):
    def test_convert_docx_returns_downloadable_word_document(self):
        encoded = base64.b64encode(_build_docx(TEXT)).decode("ascii")

        result = convert_docx_to_journal_format(
            {
                "journal": "Journal of Translational Medicine",
                "fileName": "melanoma.docx",
                "docxBase64": encoded,
            }
        )

        self.assertEqual(result["journal"], "Journal of Translational Medicine")
        self.assertTrue(result["fileName"].endswith("-journal-of-translational-medicine-formatted.docx"))
        self.assertGreater(result["extractedWordCount"], 20)
        self.assertIn("formatted submission draft", result["formattedPreview"])
        self.assertGreater(len(base64.b64decode(result["convertedDocxBase64"])), 500)

    def test_convert_docx_requires_journal(self):
        encoded = base64.b64encode(_build_docx(TEXT)).decode("ascii")

        with self.assertRaises(ValueError):
            convert_docx_to_journal_format({"docxBase64": encoded})

    def test_convert_docx_preserves_full_manuscript_body(self):
        long_methods = " ".join(["methods detail"] * 900)
        long_results = " ".join(["results finding"] * 900)
        long_discussion = " ".join(["discussion implication"] * 900)
        manuscript = f"""
Title: Long manuscript preservation test

Abstract: This manuscript tests whether conversion keeps the full article body instead of only short summaries.

Methods: {long_methods}

Results: {long_results}

Discussion: {long_discussion}
"""
        encoded = base64.b64encode(_build_docx(manuscript)).decode("ascii")

        result = convert_docx_to_journal_format(
            {
                "journal": "PLOS ONE",
                "fileName": "long-manuscript.docx",
                "docxBase64": encoded,
            }
        )
        converted_text = _extract_docx_text(base64.b64decode(result["convertedDocxBase64"]))

        self.assertGreater(result["extractedWordCount"], 5000)
        self.assertGreater(len(converted_text.split()), 5000)
        self.assertIn("methods detail", converted_text)
        self.assertIn("results finding", converted_text)
        self.assertIn("discussion implication", converted_text)

    def test_convert_docx_preserves_tables_and_reports_count(self):
        encoded = base64.b64encode(_docx_with_table()).decode("ascii")

        result = convert_docx_to_journal_format(
            {
                "journal": "JAMIA",
                "fileName": "table-manuscript.docx",
                "docxBase64": encoded,
            }
        )
        converted = base64.b64decode(result["convertedDocxBase64"])
        converted_text = _extract_docx_text(converted)

        self.assertEqual(result["tableCount"], 1)
        self.assertIn("Cohort size", converted_text)
        self.assertIn("184", converted_text)
        self.assertTrue(any("Some tables may be missing captions" in warning for warning in result["captionWarnings"]))
        self.assertIn("<w:tbl", _read_document_xml(converted))

    def test_convert_docx_preserves_media_and_reports_figure_count(self):
        encoded = base64.b64encode(_docx_with_media()).decode("ascii")

        result = convert_docx_to_journal_format(
            {
                "journal": "npj Digital Medicine",
                "fileName": "figure-manuscript.docx",
                "docxBase64": encoded,
            }
        )
        converted = base64.b64decode(result["convertedDocxBase64"])

        self.assertEqual(result["figureCount"], 1)
        self.assertTrue(any("Some figures may be missing captions" in warning for warning in result["captionWarnings"]))
        with zipfile.ZipFile(io.BytesIO(converted)) as archive:
            self.assertIn("word/media/image1.png", archive.namelist())

    def test_ieee_access_applies_two_column_layout(self):
        encoded = base64.b64encode(_build_docx(TEXT)).decode("ascii")

        result = convert_docx_to_journal_format(
            {
                "journal": "IEEE Access",
                "fileName": "ieee.docx",
                "docxBase64": encoded,
            }
        )
        document_xml = _read_document_xml(base64.b64decode(result["convertedDocxBase64"]))

        self.assertEqual(result["layoutMode"], "IEEE two-column technical layout")
        self.assertIn('w:num="2"', document_xml)

    def test_plos_one_remains_single_column(self):
        encoded = base64.b64encode(_build_docx(TEXT)).decode("ascii")

        result = convert_docx_to_journal_format(
            {
                "journal": "PLOS ONE",
                "fileName": "plos.docx",
                "docxBase64": encoded,
            }
        )
        document_xml = _read_document_xml(base64.b64decode(result["convertedDocxBase64"]))

        self.assertEqual(result["layoutMode"], "single-column submission manuscript")
        self.assertIn('w:num="1"', document_xml)

def _docx_with_table() -> bytes:
    with zipfile.ZipFile(io.BytesIO(_build_docx(TEXT))) as source:
        entries = {name: source.read(name) for name in source.namelist()}

    document_xml = entries["word/document.xml"].decode("utf-8")
    table_xml = """
<w:tbl>
  <w:tr>
    <w:tc><w:p><w:r><w:t>Measure</w:t></w:r></w:p></w:tc>
    <w:tc><w:p><w:r><w:t>Value</w:t></w:r></w:p></w:tc>
  </w:tr>
  <w:tr>
    <w:tc><w:p><w:r><w:t>Cohort size</w:t></w:r></w:p></w:tc>
    <w:tc><w:p><w:r><w:t>184</w:t></w:r></w:p></w:tc>
  </w:tr>
</w:tbl>
"""
    entries["word/document.xml"] = document_xml.replace("<w:sectPr>", f"{table_xml}<w:sectPr>").encode("utf-8")
    return _zip_entries(entries)


def _docx_with_media() -> bytes:
    with zipfile.ZipFile(io.BytesIO(_build_docx(TEXT))) as source:
        entries = {name: source.read(name) for name in source.namelist()}
    entries["word/media/image1.png"] = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return _zip_entries(entries)


def _zip_entries(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def _read_document_xml(docx_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


if __name__ == "__main__":
    unittest.main()
