# Biomedical Journal Submission Assistant

Production-oriented scaffold for a biomedical manuscript submission assistant.

The app accepts an uploaded `.docx`, `.txt`, or LaTeX `.tex` manuscript, or a
pasted abstract/manuscript narrative. It recommends journals with evidence,
estimates fit/acceptance likelihood as a heuristic, reviews acceptance risks,
and converts an uploaded Word `.docx` manuscript into the selected journal's
structured submission format. It is intentionally runnable without external AI
or PubMed credentials so the core workflow can be tested locally.

## Features

- Upload intake for Word `.docx`, plain text `.txt`, and LaTeX `.tex/.latex`.
- Abstract/manuscript extraction into an editable analysis field.
- Journal recommendations with fit evidence and heuristic acceptance-likelihood scoring.
- Reviewer-style comments, revision guidance, and cover-letter drafting.
- Selected-journal Word `.docx` conversion with formatting checklist, warnings, and downloadable output.
- Local-first deterministic worker logic with seams for future LLM and PubMed integrations.

## Stack

- Next.js app router for the product UI and API route orchestration.
- Python worker module for manuscript parsing, review generation, scoring, and
  PubMed-ready journal matching boundaries.
- Word `.docx` parsing and generation through Python standard-library ZIP/XML
  handling for the first local formatter.
- Provider-agnostic AI and NCBI integration seams via environment variables.

## Local Development

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

Use the workflow in order:

1. Upload `.docx`, `.txt`, or `.tex`, or paste an abstract directly.
2. Click **Find journals**.
3. Select one of the recommended journals.
4. Upload a `.docx` manuscript for the selected journal formatter.
5. Click **Convert Word document** and download the formatted `.docx`.

Run worker tests:

```bash
npm run test:worker
```

Run a production build:

```bash
npm run build
```

## Project Structure

```text
app/
  api/analyze/   Journal matching and reviewer workflow route
  api/convert/   Selected-journal Word conversion route
  api/extract/   Upload extraction route for .docx, .txt, and .tex
  page.tsx       Main submission-assistant workspace
worker/
  biomed_assistant/
    analyzer.py   Manuscript extraction, journal ranking, and review comments
    converter.py  Word parsing and journal-format document generation
    extractor.py  Upload text extraction for supported source formats
tests/            Python worker tests
```

## Product Claim Boundary

The journal score is labeled as an estimated fit and acceptance-likelihood
heuristic. PubMed does not include journal submission outcomes, so this scaffold
does not claim to calculate a true acceptance probability.

## Privacy Posture

Manuscripts are treated as confidential unpublished research IP. The scaffold
does not persist uploaded manuscript text by default, and production deployment
should keep raw manuscript content out of analytics, prompt debug logs, and
third-party training flows.
