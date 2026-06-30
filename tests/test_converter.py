import base64
import unittest

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


if __name__ == "__main__":
    unittest.main()
