import type {
  ApprovedFaq,
  ApprovedFaqDraft,
  ApprovedFaqLookup,
  ApprovedFaqStatus,
} from "./contracts";

const REQUEST_TIMEOUT_MILLISECONDS = 15_000;
const FAQ_PATH = "/api/v1/development/approved-faqs";

export class ApprovedFaqApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApprovedFaqApiError";
    this.status = status;
  }
}

export async function listApprovedFaqs(
  apiBaseUrl: string,
): Promise<ApprovedFaq[]> {
  const body = await requestJson(`${apiBaseUrl}${FAQ_PATH}`);
  if (!Array.isArray(body)) throw invalidResponse();
  return body.map(parseApprovedFaq);
}

export async function createApprovedFaq(
  apiBaseUrl: string,
  draft: ApprovedFaqDraft,
): Promise<ApprovedFaq> {
  const body = await requestJson(`${apiBaseUrl}${FAQ_PATH}`, {
    method: "POST",
    body: JSON.stringify({
      question: draft.question.trim(),
      approved_answer: draft.approvedAnswer.trim(),
      status: "INACTIVE",
    }),
  });
  return parseApprovedFaq(body);
}

export async function updateApprovedFaq(
  apiBaseUrl: string,
  faq: ApprovedFaq,
  draft: ApprovedFaqDraft,
): Promise<ApprovedFaq> {
  const body = await requestJson(`${apiBaseUrl}${FAQ_PATH}/${faq.id}`, {
    method: "PUT",
    body: JSON.stringify({
      question: draft.question.trim(),
      approved_answer: draft.approvedAnswer.trim(),
      expected_row_version: faq.rowVersion,
    }),
  });
  return parseApprovedFaq(body);
}

export async function setApprovedFaqStatus(
  apiBaseUrl: string,
  faq: ApprovedFaq,
  status: ApprovedFaqStatus,
): Promise<ApprovedFaq> {
  const action = status === "ACTIVE" ? "activate" : "deactivate";
  const body = await requestJson(
    `${apiBaseUrl}${FAQ_PATH}/${faq.id}/${action}`,
    {
      method: "POST",
      body: JSON.stringify({ expected_row_version: faq.rowVersion }),
    },
  );
  return parseApprovedFaq(body);
}

export async function previewApprovedFaqLookup(
  apiBaseUrl: string,
  query: string,
): Promise<ApprovedFaqLookup> {
  const body = await requestJson(`${apiBaseUrl}${FAQ_PATH}/lookup`, {
    method: "POST",
    body: JSON.stringify({ query }),
  });
  return parseApprovedFaqLookup(body);
}

export async function lookupConversationApprovedFaq(
  apiBaseUrl: string,
  conversationSessionId: string,
  query: string,
): Promise<ApprovedFaqLookup> {
  const body = await requestJson(
    `${apiBaseUrl}/api/v1/development/conversation-sessions/` +
      `${conversationSessionId}/approved-faq-lookup`,
    {
      method: "POST",
      body: JSON.stringify({ query }),
    },
  );
  return parseApprovedFaqLookup(body);
}

export function parseApprovedFaq(body: unknown): ApprovedFaq {
  if (!isRecord(body)) throw invalidResponse();
  const id = requiredString(body.id);
  const agencyId = requiredString(body.agency_id);
  const question = requiredString(body.question);
  const approvedAnswer = requiredString(body.approved_answer);
  const createdAt = requiredString(body.created_at);
  const updatedAt = requiredString(body.updated_at);
  if (
    id === undefined ||
    agencyId === undefined ||
    question === undefined ||
    approvedAnswer === undefined ||
    createdAt === undefined ||
    updatedAt === undefined ||
    (body.status !== "ACTIVE" && body.status !== "INACTIVE") ||
    typeof body.row_version !== "number"
  ) {
    throw invalidResponse();
  }
  return {
    id,
    agencyId,
    question,
    approvedAnswer,
    status: body.status,
    rowVersion: body.row_version,
    createdAt,
    updatedAt,
  };
}

export function parseApprovedFaqLookup(body: unknown): ApprovedFaqLookup {
  if (!isRecord(body) || typeof body.matched !== "boolean") {
    throw invalidResponse();
  }
  const fallbackMessage = requiredString(body.fallback_message);
  if (fallbackMessage === undefined) throw invalidResponse();
  let answer: string | null = null;
  if (body.answer !== null) {
    const parsedAnswer = requiredString(body.answer);
    if (parsedAnswer === undefined) throw invalidResponse();
    answer = parsedAnswer;
  }
  let source: ApprovedFaqLookup["source"] = null;
  if (body.source !== null) {
    if (!isRecord(body.source)) throw invalidResponse();
    const faqId = requiredString(body.source.faq_id);
    const question = requiredString(body.source.question);
    if (
      faqId === undefined ||
      question === undefined ||
      typeof body.source.row_version !== "number"
    ) {
      throw invalidResponse();
    }
    source = { faqId, question, rowVersion: body.source.row_version };
  }
  if (body.matched !== (answer !== null && source !== null)) {
    throw invalidResponse();
  }
  return { matched: body.matched, answer, fallbackMessage, source };
}

async function requestJson(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, {
    ...init,
    cache: "no-store",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MILLISECONDS),
  });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  if (!response.ok) {
    const error =
      isRecord(body) && isRecord(body.error) ? body.error : undefined;
    throw new ApprovedFaqApiError(
      response.status,
      (error && requiredString(error.message)) ??
        "The approved FAQ request could not be completed",
    );
  }
  return body;
}

function invalidResponse(): ApprovedFaqApiError {
  return new ApprovedFaqApiError(
    502,
    "The approved FAQ service returned invalid data",
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requiredString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}
