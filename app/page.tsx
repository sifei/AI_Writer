"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpenCheck,
  ClipboardCheck,
  Download,
  FileText,
  Lightbulb,
  LockKeyhole,
  MessageSquareText,
  Search,
  ShieldCheck,
  Sparkles,
  Upload
} from "lucide-react";
import type { AnalysisResult, ConversionResult, ExtractedUpload } from "@/lib/types";

const sampleNarrative = `Title: Immune-metabolic signatures associated with early response to checkpoint inhibition in metastatic melanoma

Abstract: Checkpoint inhibition improves outcomes for patients with metastatic melanoma, but early biomarkers of durable response remain incomplete. We conducted a prospective observational cohort study of 184 adults receiving anti-PD-1 based therapy across three academic centers. Peripheral blood samples were collected at baseline and week four. Multiplex cytokine panels, metabolomics, and clinical covariates were integrated using regularized regression and pathway enrichment. Durable response at twelve months was associated with lower baseline IL-8, preserved tryptophan metabolism, and early expansion of activated CD8 T cell signatures. The model achieved an optimism-corrected AUC of 0.78. Limitations include moderate sample size, incomplete external validation, and underrepresentation of patients with autoimmune comorbidity.

Methods: Adults with unresectable stage III or IV melanoma initiating checkpoint inhibition were enrolled from 2021 to 2024. The primary endpoint was durable clinical response at twelve months by RECIST 1.1. Institutional review board approval and written informed consent were obtained. Missing covariates were handled with multiple imputation. Models were adjusted for age, stage, lactate dehydrogenase, performance status, and treatment regimen.

Results: Among 184 participants, 72 achieved durable response. The integrated immune-metabolic model outperformed clinical covariates alone. Calibration was acceptable after bootstrap correction. Sensitivity analyses excluding combination therapy showed similar directionality.

Discussion: Early immune-metabolic changes may help identify patients likely to benefit from checkpoint inhibition. External validation and mechanistic studies are needed before clinical deployment.`;

const articleTypes = ["Original Research", "Systematic Review", "Case Report", "Clinical Trial", "Methods Paper"];

export default function Home() {
  const [title, setTitle] = useState("");
  const [narrative, setNarrative] = useState(sampleNarrative);
  const [articleType, setArticleType] = useState(articleTypes[0]);
  const [targetField, setTargetField] = useState("Oncology / immunotherapy");
  const [constraints, setConstraints] = useState("Open access preferred\nFast review useful");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [selectedJournal, setSelectedJournal] = useState("");
  const [docxFile, setDocxFile] = useState<File | null>(null);
  const [conversion, setConversion] = useState<ConversionResult | null>(null);
  const [sourceUpload, setSourceUpload] = useState<ExtractedUpload | null>(null);
  const [error, setError] = useState("");
  const [conversionError, setConversionError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);

  const wordCount = useMemo(() => {
    return narrative.trim().split(/\s+/).filter(Boolean).length;
  }, [narrative]);

  async function analyze() {
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          narrative,
          articleType,
          targetField,
          constraints: constraints
            .split("\n")
            .map((item) => item.trim())
            .filter(Boolean)
        })
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Analysis failed");
      }

      const analysis = payload as AnalysisResult;
      setResult(analysis);
      setSelectedJournal(analysis.recommendations[0]?.journal || "");
      setConversion(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis failed");
    } finally {
      setIsLoading(false);
    }
  }

  async function extractSourceFile(file: File | null) {
    if (!file) {
      return;
    }

    setIsExtracting(true);
    setUploadError("");

    try {
      const fileBase64 = await fileToBase64(file);
      const response = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fileName: file.name,
          mimeType: file.type,
          fileBase64
        })
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "File extraction failed");
      }

      const extracted = payload as ExtractedUpload;
      setSourceUpload(extracted);
      setNarrative(extracted.text);
      setResult(null);
      setConversion(null);
      setSelectedJournal("");
    } catch (caught) {
      setUploadError(caught instanceof Error ? caught.message : "File extraction failed");
    } finally {
      setIsExtracting(false);
    }
  }

  async function convertDocument() {
    if (!docxFile) {
      setConversionError("Upload a Word .docx document first.");
      return;
    }

    if (!selectedJournal) {
      setConversionError("Select a target journal first.");
      return;
    }

    setIsConverting(true);
    setConversionError("");

    try {
      const docxBase64 = await fileToBase64(docxFile);
      const response = await fetch("/api/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          journal: selectedJournal,
          fileName: docxFile.name,
          docxBase64
        })
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Conversion failed");
      }

      setConversion(payload as ConversionResult);
    } catch (caught) {
      setConversionError(caught instanceof Error ? caught.message : "Conversion failed");
    } finally {
      setIsConverting(false);
    }
  }

  function downloadConvertedDocx() {
    if (!conversion) {
      return;
    }

    const bytes = Uint8Array.from(atob(conversion.convertedDocxBase64), (char) => char.charCodeAt(0));
    const blob = new Blob([bytes], {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = conversion.fileName;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="shell">
      <section className="topbar">
        <div className="brand">
          <div className="brandMark">
            <BookOpenCheck size={24} />
          </div>
          <div>
            <p className="eyebrow">Biomedical Submission Assistant</p>
            <h1>Manuscript fit, review, and revision workspace</h1>
          </div>
        </div>
        <div className="securityPill">
          <LockKeyhole size={16} />
          Confidential manuscript mode
        </div>
      </section>

      <section className="workspace">
        <form
          className="inputPanel"
          onSubmit={(event) => {
            event.preventDefault();
            analyze();
          }}
        >
          <div className="panelHeader">
            <div>
              <h2>Manuscript Intake</h2>
              <p>Upload Word, plain text, or LaTeX files, or paste an abstract directly.</p>
            </div>
            <FileText size={22} />
          </div>

          <label className="sourceUpload">
            <Upload size={22} />
            <span>
              {isExtracting
                ? "Extracting manuscript text..."
                : sourceUpload
                  ? `${sourceUpload.fileName} · ${sourceUpload.wordCount.toLocaleString()} words`
                  : "Upload .docx, .txt, or .tex"}
            </span>
            <input
              type="file"
              accept=".docx,.txt,.tex,.latex,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => extractSourceFile(event.target.files?.[0] || null)}
            />
          </label>

          {sourceUpload ? (
            <div className="uploadReport">
              {sourceUpload.warnings.map((warning) => (
                <span key={warning}>{warning}</span>
              ))}
            </div>
          ) : null}

          {uploadError ? <p className="errorText">{uploadError}</p> : null}

          <label>
            Working title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Optional if included in manuscript text"
            />
          </label>

          <div className="twoColumn">
            <label>
              Article type
              <select value={articleType} onChange={(event) => setArticleType(event.target.value)}>
                {articleTypes.map((type) => (
                  <option key={type}>{type}</option>
                ))}
              </select>
            </label>

            <label>
              Target field
              <input value={targetField} onChange={(event) => setTargetField(event.target.value)} />
            </label>
          </div>

          <label>
            Submission constraints
            <textarea
              className="smallTextArea"
              value={constraints}
              onChange={(event) => setConstraints(event.target.value)}
            />
          </label>

          <label>
            Abstract or manuscript narrative
            <textarea
              className="manuscriptBox"
              value={narrative}
              onChange={(event) => setNarrative(event.target.value)}
            />
          </label>

          <div className="formFooter">
            <span>{wordCount.toLocaleString()} words</span>
            <button type="submit" disabled={isLoading}>
              {isLoading ? "Finding journals..." : "Find journals"}
              <Sparkles size={18} />
            </button>
          </div>

          {error ? <p className="errorText">{error}</p> : null}

          <div className="privacyNotice">
            <ShieldCheck size={18} />
            <span>Raw manuscripts are not persisted by this scaffold or sent to analytics.</span>
          </div>
        </form>

        <section className="resultsPanel">
          {!result ? (
            <div className="emptyState">
              <div className="emptyIcon">
                <Search size={38} />
              </div>
              <h2>Paste an abstract to generate journal recommendations</h2>
              <p>
                The workflow returns ranked journals, reviewer comments, formatting requirements,
                and a Word conversion step for the selected journal.
              </p>
            </div>
          ) : (
            <div className="resultsStack">
              <div className="summaryBand">
                <div>
                    <p className="eyebrow">Extracted Abstract</p>
                  <h2>{result.manuscript.title}</h2>
                  <p>{result.manuscript.abstract}</p>
                </div>
                <div className="scoreDial">
                  <span>{result.manuscript.completenessScore}</span>
                  <small>Completeness</small>
                </div>
              </div>

              <div className="cardsGrid">
                <article className="card">
                  <div className="cardTitle">
                    <ClipboardCheck size={18} />
                    <h3>Reviewer Comments</h3>
                  </div>
                  {result.reviewerComments.map((comment) => (
                    <div className="comment" key={`${comment.area}-${comment.comment}`}>
                      <strong>{comment.severity.toUpperCase()} · {comment.area}</strong>
                      <p>{comment.comment}</p>
                      <span>{comment.suggestion}</span>
                    </div>
                  ))}
                </article>

                <article className="card">
                  <div className="cardTitle">
                    <Lightbulb size={18} />
                    <h3>Guided Revision</h3>
                  </div>
                  {result.revisionGuide.map((item) => (
                    <div className="comment" key={item.prompt}>
                      <strong>{item.prompt}</strong>
                      <p>{item.rationale}</p>
                      <span>{item.rephrasedExample}</span>
                    </div>
                  ))}
                </article>
              </div>

              <section className="recommendations">
                <div className="sectionHeader">
                  <div>
                    <p className="eyebrow">PubMed-backed Strategy</p>
                    <h2>Journal Recommendations</h2>
                  </div>
                  <span className="claimPill">
                    <AlertTriangle size={16} />
                    Heuristic, not guaranteed
                  </span>
                </div>

                {result.recommendations.map((journal) => (
                  <article
                    className={selectedJournal === journal.journal ? "journalCard selectedJournal" : "journalCard"}
                    key={journal.journal}
                  >
                    <div className="journalTop">
                      <div>
                        <h3>{journal.journal}</h3>
                        <p>{journal.scope}</p>
                      </div>
                      <div className="journalScore">
                        <span>{journal.estimatedFitAndAcceptanceLikelihood}%</span>
                        <small>
                          {journal.confidenceBand[0]}-{journal.confidenceBand[1]}% band
                        </small>
                      </div>
                    </div>
                    <div className="evidenceGrid">
                      <div>
                        <h4>Evidence</h4>
                        {journal.evidence.map((item) => <p key={item}>{item}</p>)}
                      </div>
                      <div>
                        <h4>Formatting checklist</h4>
                        {journal.formattingChecklist.map((item) => <p key={item}>{item}</p>)}
                      </div>
                    </div>
                    <div className="factorRow">
                      <span>Raises: {journal.factorsRaised.join(", ")}</span>
                      <span>Lowers: {journal.factorsLowered.join(", ")}</span>
                    </div>
                    <button
                      className="secondaryButton"
                      type="button"
                      onClick={() => {
                        setSelectedJournal(journal.journal);
                        setConversion(null);
                      }}
                    >
                      Use this journal format
                    </button>
                  </article>
                ))}
              </section>

              <section className="conversionPanel">
                <div className="sectionHeader">
                  <div>
                    <p className="eyebrow">Word Document Conversion</p>
                    <h2>Convert to selected journal format</h2>
                  </div>
                  <span className="claimPill">
                    <FileText size={16} />
                    {selectedJournal || "No journal selected"}
                  </span>
                </div>

                <div className="conversionGrid">
                  <label className="fileDrop">
                    <Upload size={22} />
                    <span>{docxFile ? docxFile.name : "Upload manuscript .docx"}</span>
                    <input
                      type="file"
                      accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      onChange={(event) => {
                        setDocxFile(event.target.files?.[0] || null);
                        setConversion(null);
                      }}
                    />
                  </label>

                  <button type="button" onClick={convertDocument} disabled={isConverting || !selectedJournal}>
                    {isConverting ? "Converting..." : "Convert Word document"}
                    <FileText size={18} />
                  </button>
                </div>

                {conversionError ? <p className="errorText">{conversionError}</p> : null}

                {conversion ? (
                  <div className="conversionResult">
                    <div className="conversionActions">
                      <div>
                        <h3>{conversion.fileName}</h3>
                        <p>
                          {conversion.extractedWordCount.toLocaleString()} words · {conversion.tableCount} tables ·{" "}
                          {conversion.figureCount} figures/media · {conversion.layoutMode}
                        </p>
                      </div>
                      <button type="button" onClick={downloadConvertedDocx}>
                        Download .docx
                        <Download size={18} />
                      </button>
                    </div>

                    <div className="evidenceGrid">
                      <div>
                        <h4>Applied rules</h4>
                        {conversion.appliedRules.map((rule) => <p key={rule}>{rule}</p>)}
                      </div>
                      <div>
                        <h4>Warnings</h4>
                        {conversion.warnings.map((warning) => <p key={warning}>{warning}</p>)}
                        {conversion.captionWarnings.length ? <h4>Caption checks</h4> : null}
                        {conversion.captionWarnings.map((warning) => <p key={warning}>{warning}</p>)}
                      </div>
                    </div>

                    <pre>{conversion.formattedPreview}</pre>
                  </div>
                ) : null}
              </section>

              <article className="coverLetter">
                <div className="cardTitle">
                  <MessageSquareText size={18} />
                  <h3>Cover Letter Draft</h3>
                </div>
                <pre>{result.coverLetterDraft}</pre>
                <p>{result.claimBoundary}</p>
              </article>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",")[1] : value);
    };
    reader.onerror = () => reject(reader.error || new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}
