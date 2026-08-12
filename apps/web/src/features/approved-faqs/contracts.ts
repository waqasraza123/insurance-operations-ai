export type ApprovedFaqStatus = "ACTIVE" | "INACTIVE";

export type ApprovedFaq = Readonly<{
  id: string;
  agencyId: string;
  question: string;
  approvedAnswer: string;
  status: ApprovedFaqStatus;
  rowVersion: number;
  createdAt: string;
  updatedAt: string;
}>;

export type ApprovedFaqDraft = Readonly<{
  question: string;
  approvedAnswer: string;
}>;

export type ApprovedFaqSource = Readonly<{
  faqId: string;
  question: string;
  rowVersion: number;
}>;

export type ApprovedFaqLookup = Readonly<{
  matched: boolean;
  answer: string | null;
  fallbackMessage: string;
  source: ApprovedFaqSource | null;
}>;
