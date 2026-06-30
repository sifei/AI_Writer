import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "were",
    "was",
    "are",
    "our",
    "using",
    "study",
    "patients",
    "results",
    "methods",
    "clinical",
    "response",
    "between",
    "into",
    "their",
}

SECTION_NAMES = [
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "limitations",
    "conclusion",
    "references",
]

BUILT_IN_JOURNAL_PROFILES = [
    {
        "journal": "BMC Medicine",
        "scope": "Broad translational and clinical medicine with open-access publication model.",
        "keywords": {
            "clinical",
            "cohort",
            "biomarker",
            "translational",
            "medicine",
            "prospective",
            "observational",
            "validation",
        },
        "competitiveness": 0.78,
        "checklist": [
            "Use a structured abstract when possible.",
            "Add transparent ethics, consent, funding, competing interests, and data availability statements.",
            "Emphasize clinical relevance and reproducibility in the cover letter.",
        ],
    },
    {
        "journal": "Journal of Translational Medicine",
        "scope": "Mechanistic and clinical translation studies connecting biomarkers to patient outcomes.",
        "keywords": {
            "biomarker",
            "immune",
            "metabolic",
            "translational",
            "pathway",
            "cohort",
            "oncology",
            "validation",
        },
        "competitiveness": 0.68,
        "checklist": [
            "Make the translational mechanism explicit in the abstract and discussion.",
            "Report assay platforms, preprocessing, missing-data handling, and model validation.",
            "Include limitations around generalizability and clinical deployment.",
        ],
    },
    {
        "journal": "PLOS ONE",
        "scope": "Methodologically sound multidisciplinary research where technical rigor is central.",
        "keywords": {
            "cohort",
            "regression",
            "model",
            "observational",
            "analysis",
            "data",
            "method",
            "reproducibility",
        },
        "competitiveness": 0.52,
        "checklist": [
            "Lead with methodological validity rather than perceived impact.",
            "Provide complete data availability, code availability, and reporting checklist details.",
            "Avoid overstating clinical adoption before external validation.",
        ],
    },
    {
        "journal": "Frontiers in Immunology",
        "scope": "Immunology studies spanning mechanisms, biomarkers, and immune-mediated disease.",
        "keywords": {
            "immune",
            "immunology",
            "cytokine",
            "checkpoint",
            "cd8",
            "therapy",
            "pathway",
            "melanoma",
        },
        "competitiveness": 0.58,
        "checklist": [
            "Frame immune mechanism and pathway interpretation clearly.",
            "Clarify immune assays, gating or platform details, and multiple-testing control.",
            "Align discussion with immunology readers before clinical implementation claims.",
        ],
    },
]


def get_journal_profiles() -> List[Dict]:
    profiles_by_name = {profile["journal"]: profile for profile in BUILT_IN_JOURNAL_PROFILES}
    profiles_dir = Path(__file__).resolve().parents[2] / "data" / "journal_profiles"

    if profiles_dir.exists():
        for path in sorted(profiles_dir.glob("*.json")):
            with path.open(encoding="utf-8") as profile_file:
                profile = _profile_from_json(json.load(profile_file))
            profiles_by_name[profile["journal"]] = profile

    return list(profiles_by_name.values())

def analyze_submission(payload: Dict) -> Dict:
    narrative = payload.get("narrative", "").strip()
    if len(narrative) < 200:
        raise ValueError("Manuscript narrative is too short for analysis.")

    title = _extract_title(narrative, payload.get("title"))
    article_type = payload.get("articleType") or _infer_article_type(narrative)
    keywords = _keywords(narrative, payload.get("targetField", ""))
    sections = _sections(narrative)
    claims = _claims(narrative)
    methods = _methods(narrative)
    limitations = _limitations(narrative)
    completeness = _completeness_score(sections, methods, limitations, narrative)

    manuscript = {
        "title": title,
        "abstract": _abstract(narrative),
        "articleType": article_type,
        "keywords": keywords,
        "sections": sections,
        "claims": claims,
        "methods": methods,
        "limitations": limitations,
        "completenessScore": completeness,
    }

    recommendations = _recommend_journals(keywords, narrative, article_type, completeness)

    return {
        "manuscript": manuscript,
        "reviewerComments": _reviewer_comments(manuscript, narrative),
        "recommendations": recommendations,
        "revisionGuide": _revision_guide(manuscript, recommendations),
        "coverLetterDraft": _cover_letter(title, manuscript, recommendations[0]),
        "privacyNotice": (
            "Manuscripts are treated as confidential unpublished research IP; raw text should not be logged, "
            "used for training, or retained beyond the configured workspace policy."
        ),
        "claimBoundary": (
            "Estimated fit and acceptance likelihood is a heuristic derived from manuscript completeness, "
            "scope match, article type, and public publication-pattern proxies. It is not a guaranteed "
            "journal acceptance probability."
        ),
    }


def _extract_title(text: str, provided: str = "") -> str:
    if provided and provided.strip():
        return provided.strip()

    title_match = re.search(r"(?im)^title:\s*(.+)$", text)
    if title_match:
        return title_match.group(1).strip()

    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line[:140] if first_line else "Untitled biomedical manuscript"


def _infer_article_type(text: str) -> str:
    lowered = text.lower()
    if "randomized" in lowered or "trial" in lowered:
        return "Clinical Trial"
    if "systematic review" in lowered or "meta-analysis" in lowered:
        return "Systematic Review"
    if "case report" in lowered:
        return "Case Report"
    return "Original Research"


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower())


def _keywords(text: str, field: str) -> List[str]:
    words = [word for word in _tokens(f"{field} {text}") if word not in STOPWORDS]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(12)]


def _abstract(text: str) -> str:
    match = re.search(
        r"(?is)abstract:\s*(.+?)(?:\n\s*(?:methods|introduction|results|discussion|limitations):|$)",
        text,
    )
    if match:
        return _trim_sentence(match.group(1).strip(), 560)
    return _trim_sentence(text.strip(), 560)


def _sections(text: str) -> List[Dict]:
    found = []
    pattern = re.compile(
        r"(?ims)^\s*(abstract|introduction|methods|results|discussion|limitations|conclusion|references):\s*(.*?)(?=^\s*(?:abstract|introduction|methods|results|discussion|limitations|conclusion|references):|\Z)"
    )

    for name, body in pattern.findall(text):
        found.append(
            {
                "name": name.title(),
                "wordCount": len(body.split()),
                "summary": _trim_sentence(body.strip(), 180),
            }
        )

    if found:
        return found

    return [
        {
            "name": "Narrative",
            "wordCount": len(text.split()),
            "summary": _trim_sentence(text, 180),
        }
    ]


def _claims(text: str) -> List[str]:
    claim_patterns = [
        r"(?i)(?:we found|we demonstrate|we show|was associated with|were associated with|improves?|outperformed)[^.]*\.",
        r"(?i)(?:model achieved|achieved an|sensitivity analyses)[^.]*\.",
    ]
    return _collect_sentences(text, claim_patterns, 4) or [
        "Clarify the manuscript's primary claim in one direct sentence."
    ]


def _methods(text: str) -> List[str]:
    method_terms = [
        "cohort",
        "randomized",
        "regression",
        "imputation",
        "bootstrap",
        "prospective",
        "retrospective",
        "assay",
        "metabolomics",
        "enrolled",
    ]
    sentences = _sentences(text)
    hits = [sentence for sentence in sentences if any(term in sentence.lower() for term in method_terms)]
    return [_trim_sentence(sentence, 180) for sentence in hits[:5]] or [
        "Add study design, population, endpoints, statistical plan, and ethics approval."
    ]


def _limitations(text: str) -> List[str]:
    sentences = _sentences(text)
    hits = [
        sentence
        for sentence in sentences
        if any(term in sentence.lower() for term in ["limitation", "limited", "underrepresentation", "external validation", "generalizability"])
    ]
    return [_trim_sentence(sentence, 180) for sentence in hits[:4]] or [
        "State the main limitations, including sample size, bias, validation, and generalizability."
    ]


def _completeness_score(sections: List[Dict], methods: List[str], limitations: List[str], text: str) -> int:
    present_sections = {section["name"].lower() for section in sections}
    score = 35
    score += 8 * len(present_sections.intersection(SECTION_NAMES))
    score += 12 if methods and "Add study design" not in methods[0] else 0
    score += 10 if limitations and "State the main limitations" not in limitations[0] else 0
    score += 8 if re.search(r"(?i)ethics|institutional review|consent|irb", text) else 0
    score += 7 if re.search(r"(?i)data availability|code availability|missing|imputation|bootstrap", text) else 0
    return max(0, min(96, score))


def _reviewer_comments(manuscript: Dict, text: str) -> List[Dict]:
    comments = []

    if manuscript["completenessScore"] < 78:
        comments.append(
            {
                "severity": "major",
                "area": "Reporting completeness",
                "comment": "The draft does not yet expose enough submission-critical details for confident editorial triage.",
                "suggestion": "Add explicit design, endpoint, ethics, statistics, data availability, and limitations statements.",
            }
        )

    if not re.search(r"(?i)external validation|validation cohort|independent cohort", text):
        comments.append(
            {
                "severity": "major",
                "area": "Validation",
                "comment": "The acceptance risk is higher because external validation is not clearly established.",
                "suggestion": "Reframe clinical claims as hypothesis-generating unless independent validation is available.",
            }
        )

    if re.search(r"(?i)model|auc|prediction|classifier", text) and not re.search(r"(?i)calibration|decision curve|bootstrap", text):
        comments.append(
            {
                "severity": "major",
                "area": "Predictive modeling",
                "comment": "Prediction claims need calibration, optimism correction, and transparent feature handling.",
                "suggestion": "Add model-development details and report calibration alongside discrimination metrics.",
            }
        )

    comments.append(
        {
            "severity": "minor",
            "area": "Editorial positioning",
            "comment": "The strongest submission angle should be visible in the final abstract sentence and cover letter.",
            "suggestion": "State what changes for researchers, clinicians, or trial designers if the findings are confirmed.",
        }
    )

    return comments[:4]


def _recommend_journals(
    keywords: List[str], text: str, article_type: str, completeness: int
) -> List[Dict]:
    keyword_set = set(keywords)
    ranked = []

    for profile in JOURNAL_PROFILES:
        overlap = len(keyword_set.intersection(profile["keywords"]))
        topic_score = min(1.0, overlap / max(4, min(8, len(profile["keywords"]))))
        method_bonus = 0.08 if re.search(r"(?i)cohort|trial|prospective|validation|model", text) else 0
        article_bonus = 0.06 if article_type in {"Original Research", "Clinical Trial"} else 0.01
        completeness_factor = completeness / 100
        selectivity_penalty = profile["competitiveness"] * 0.18
        raw = 0.28 + topic_score * 0.38 + completeness_factor * 0.24 + method_bonus + article_bonus - selectivity_penalty
        estimate = int(round(max(0.12, min(0.82, raw)) * 100))
        band = (max(5, estimate - 12), min(92, estimate + 10))

        ranked.append(
            {
                "journal": profile["journal"],
                "scope": profile["scope"],
                "estimatedFitAndAcceptanceLikelihood": estimate,
                "confidenceBand": list(band),
                "evidence": [
                    f"{overlap} manuscript keyword(s) overlap with the cached journal profile.",
                    f"Completeness score contributes {completeness}/100 to editorial readiness.",
                    "PubMed-ready profile boundary: replace this cached profile with E-utilities and NLM Catalog evidence in production.",
                ],
                "factorsRaised": _raised_factors(overlap, completeness, article_type),
                "factorsLowered": _lowered_factors(profile["competitiveness"], text),
                "formattingChecklist": profile["checklist"],
            }
        )

    return sorted(
        ranked,
        key=lambda item: item["estimatedFitAndAcceptanceLikelihood"],
        reverse=True,
    )[:3]


def _profile_from_json(profile: Dict) -> Dict:
    recommendation_inputs = profile.get("recommendation_inputs", {})
    return {
        "journal": profile["journal"],
        "scope": profile["scope"],
        "keywords": _profile_keyword_terms(profile.get("keywords", []), profile.get("subject_areas", [])),
        "article_types": set(profile.get("article_types", [])),
        "competitiveness": recommendation_inputs.get("competitiveness", 0.65),
        "checklist": profile.get("checklist", []),
        "source_profile_id": profile.get("id"),
        "evidence_sources": profile.get("evidence_sources", []),
    }


def _profile_keyword_terms(*keyword_groups: List[str]) -> set:
    terms = set()
    for group in keyword_groups:
        for phrase in group:
            terms.add(phrase.lower())
            terms.update(token for token in _tokens(phrase) if token not in STOPWORDS)
    return terms


def _raised_factors(overlap: int, completeness: int, article_type: str) -> List[str]:
    factors = []
    if overlap:
        factors.append("scope match")
    if completeness >= 80:
        factors.append("reporting completeness")
    if article_type in {"Original Research", "Clinical Trial"}:
        factors.append("article type fit")
    return factors or ["clearer journal positioning needed"]


def _lowered_factors(competitiveness: float, text: str) -> List[str]:
    factors = []
    if competitiveness >= 0.7:
        factors.append("journal competitiveness")
    if not re.search(r"(?i)external validation|independent cohort", text):
        factors.append("limited external validation")
    if not re.search(r"(?i)data availability|code availability", text):
        factors.append("data transparency not explicit")
    return factors or ["no major lowering factor detected"]


def _revision_guide(manuscript: Dict, recommendations: List[Dict]) -> List[Dict]:
    top_journal = recommendations[0]["journal"]
    return [
        {
            "prompt": "What is the single strongest novelty claim?",
            "rationale": f"Editors at {top_journal} need the contribution to be visible before method details.",
            "rephrasedExample": "This study identifies an early, clinically measurable signal that may improve selection for subsequent validation cohorts.",
        },
        {
            "prompt": "Which limitation should be acknowledged before reviewers raise it?",
            "rationale": "Owning the constraint reduces perceived overclaiming and improves reviewer trust.",
            "rephrasedExample": "Because external validation was not completed, these findings should be interpreted as a prioritization framework rather than a deployment-ready test.",
        },
        {
            "prompt": "What reporting detail would make the analysis reproducible?",
            "rationale": "Methods transparency is a frequent acceptance-risk lever for biomedical submissions.",
            "rephrasedExample": "We prespecified endpoint definitions, handled missing covariates by multiple imputation, and evaluated optimism by bootstrap resampling.",
        },
    ]


def _cover_letter(title: str, manuscript: Dict, top_journal: Dict) -> str:
    claim = manuscript["claims"][0] if manuscript["claims"] else "The manuscript addresses a timely biomedical question."
    return (
        f"Dear Editor,\n\n"
        f"Please consider our manuscript, \"{title},\" for publication in {top_journal['journal']}. "
        f"The work is aligned with the journal's scope because {top_journal['scope'].lower()}\n\n"
        f"The central contribution is: {claim} We believe the manuscript will interest readers because it connects "
        f"biomedical evidence with a clear translational or clinical decision point.\n\n"
        f"We confirm that ethical approval, competing interests, funding, author contributions, and data availability "
        f"statements should be verified before submission.\n\n"
        f"Sincerely,\nThe authors"
    )


def _collect_sentences(text: str, patterns: Iterable[str], limit: int) -> List[str]:
    results = []
    for pattern in patterns:
        results.extend(re.findall(pattern, text))
    return [_trim_sentence(sentence, 180) for sentence in results[:limit]]


def _sentences(text: str) -> List[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _trim_sentence(text: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    trimmed = normalized[:limit].rsplit(" ", 1)[0]
    return f"{trimmed}..."


JOURNAL_PROFILES = get_journal_profiles()
