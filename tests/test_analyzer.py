import unittest

from worker.biomed_assistant.analyzer import JOURNAL_PROFILES, analyze_submission


SAMPLE = """
Title: Immune signatures and checkpoint inhibitor response in melanoma

Abstract: We conducted a prospective cohort study of adults with metastatic melanoma receiving checkpoint inhibition.
Baseline cytokines, metabolomics, and clinical covariates were integrated to predict durable response. The model achieved
an AUC of 0.78 after bootstrap correction.

Methods: Adults were enrolled across three academic centers. Institutional review board approval and written informed
consent were obtained. Missing covariates were handled with multiple imputation and models adjusted for clinical factors.

Results: Durable response was associated with lower IL-8 and preserved tryptophan metabolism.

Limitations: Limitations include moderate sample size and incomplete external validation.
"""


class AnalyzerTests(unittest.TestCase):
    def test_analyze_submission_returns_core_workflow_outputs(self):
        result = analyze_submission(
            {
                "narrative": SAMPLE,
                "articleType": "Original Research",
                "targetField": "Oncology immunotherapy",
                "constraints": ["Open access preferred"],
            }
        )

        self.assertIn("manuscript", result)
        self.assertIn("reviewerComments", result)
        self.assertIn("recommendations", result)
        self.assertIn("revisionGuide", result)
        self.assertGreaterEqual(len(result["recommendations"]), 3)
        self.assertIn("heuristic", result["claimBoundary"].lower())

    def test_recommendations_include_confidence_band_and_evidence(self):
        result = analyze_submission({"narrative": SAMPLE, "articleType": "Original Research"})
        journal = result["recommendations"][0]

        self.assertIn("estimatedFitAndAcceptanceLikelihood", journal)
        self.assertEqual(len(journal["confidenceBand"]), 2)
        self.assertGreater(len(journal["evidence"]), 0)
        self.assertLessEqual(journal["confidenceBand"][0], journal["estimatedFitAndAcceptanceLikelihood"])
        self.assertGreaterEqual(journal["confidenceBand"][1], journal["estimatedFitAndAcceptanceLikelihood"])

    def test_short_manuscript_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_submission({"narrative": "Too short."})

    def test_source_backed_profiles_are_loaded(self):
        journals = {profile["journal"] for profile in JOURNAL_PROFILES}

        self.assertIn("Journal of Biomedical Informatics", journals)
        self.assertIn("Journal of the American Medical Informatics Association", journals)
        self.assertIn("IEEE Access", journals)
        self.assertIn("npj Digital Medicine", journals)

    def test_informatics_manuscript_recommends_informatics_journals(self):
        result = analyze_submission(
            {
                "articleType": "Original Research",
                "targetField": "clinical informatics",
                "narrative": """
Title: Clinical decision support and electronic health record implementation for sepsis

Abstract: We developed and evaluated a clinical decision support system integrated with electronic
health records for sepsis detection. The study uses biomedical informatics, health informatics,
implementation science, machine learning, evaluation, public health, and clinical care workflows.
Methods include a cohort design, model validation, workflow usability evaluation, and comparison
with state of the art decision support approaches. Results show improved alert precision and
clinician adoption. Discussion addresses generalizability, privacy, security, and health system
implementation.
""",
            }
        )

        journals = {journal["journal"] for journal in result["recommendations"]}
        self.assertTrue(
            {
                "Journal of Biomedical Informatics",
                "Journal of the American Medical Informatics Association",
            }.intersection(journals)
        )


if __name__ == "__main__":
    unittest.main()
