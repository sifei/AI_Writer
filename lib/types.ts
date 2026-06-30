export type ManuscriptInput = {
  title?: string;
  narrative: string;
  articleType: string;
  targetField: string;
  constraints: string[];
};

export type ExtractedManuscript = {
  title: string;
  abstract: string;
  articleType: string;
  keywords: string[];
  sections: { name: string; wordCount: number; summary: string }[];
  claims: string[];
  methods: string[];
  limitations: string[];
  completenessScore: number;
};

export type ReviewerComment = {
  severity: "major" | "minor";
  area: string;
  comment: string;
  suggestion: string;
};

export type JournalRecommendation = {
  journal: string;
  scope: string;
  estimatedFitAndAcceptanceLikelihood: number;
  confidenceBand: [number, number];
  evidence: string[];
  factorsRaised: string[];
  factorsLowered: string[];
  formattingChecklist: string[];
};

export type ConversionResult = {
  journal: string;
  fileName: string;
  convertedDocxBase64: string;
  formattedPreview: string;
  appliedRules: string[];
  warnings: string[];
  extractedWordCount: number;
  tableCount: number;
  figureCount: number;
  captionWarnings: string[];
  layoutMode: string;
};

export type ExtractedUpload = {
  fileName: string;
  detectedType: "docx" | "txt" | "latex";
  text: string;
  wordCount: number;
  warnings: string[];
};

export type RevisionGuidance = {
  prompt: string;
  rationale: string;
  rephrasedExample: string;
};

export type AnalysisResult = {
  manuscript: ExtractedManuscript;
  reviewerComments: ReviewerComment[];
  recommendations: JournalRecommendation[];
  revisionGuide: RevisionGuidance[];
  coverLetterDraft: string;
  privacyNotice: string;
  claimBoundary: string;
};
