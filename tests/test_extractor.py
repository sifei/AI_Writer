import base64
import unittest

from worker.biomed_assistant.extractor import extract_uploaded_text


class ExtractorTests(unittest.TestCase):
    def test_extracts_plain_text_upload(self):
        text = (
            "Title: Biomarker response study\n\n"
            "Abstract: This prospective cohort study evaluates immune biomarkers in oncology patients. "
            "Methods and results are described with enough detail for journal matching."
        )
        result = extract_uploaded_text(
            {
                "fileName": "abstract.txt",
                "mimeType": "text/plain",
                "fileBase64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            }
        )

        self.assertEqual(result["detectedType"], "txt")
        self.assertIn("prospective cohort", result["text"])
        self.assertGreater(result["wordCount"], 10)

    def test_extracts_and_simplifies_latex_upload(self):
        latex = r"""
        \title{Immune signatures in melanoma}
        \begin{abstract}
        We evaluated checkpoint inhibitor response in a prospective cohort with translational biomarkers.
        The study reports methods, results, and limitations for journal matching.
        \end{abstract}
        \section{Methods}
        Adults were enrolled after consent and institutional review approval.
        """
        result = extract_uploaded_text(
            {
                "fileName": "paper.tex",
                "mimeType": "text/x-tex",
                "fileBase64": base64.b64encode(latex.encode("utf-8")).decode("ascii"),
            }
        )

        self.assertEqual(result["detectedType"], "latex")
        self.assertIn("Immune signatures in melanoma", result["text"])
        self.assertNotIn("\\section", result["text"])
        self.assertTrue(any("LaTeX" in warning for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
