import type {
  ReceptionistSettings,
  ReceptionistSettingsDraft,
} from "./contracts";
import { categoriesFromDraft } from "./settings-form";

const REQUEST_TIMEOUT_MILLISECONDS = 15_000;
const SETTINGS_PATH = "/api/v1/development/receptionist-settings";

export class ReceptionistSettingsApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ReceptionistSettingsApiError";
    this.status = status;
  }
}

export async function getReceptionistSettings(
  apiBaseUrl: string,
): Promise<ReceptionistSettings> {
  const response = await fetch(`${apiBaseUrl}${SETTINGS_PATH}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MILLISECONDS),
  });
  const body: unknown = await readJson(response);
  if (!response.ok) {
    throw apiError(response, body);
  }
  return parseReceptionistSettings(body);
}

export async function replaceReceptionistSettings(
  apiBaseUrl: string,
  draft: ReceptionistSettingsDraft,
  expectedRowVersion: number,
): Promise<ReceptionistSettings> {
  const response = await fetch(`${apiBaseUrl}${SETTINGS_PATH}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MILLISECONDS),
    body: JSON.stringify({
      public_name: draft.publicName.trim(),
      greeting: draft.greeting.trim(),
      office_hours: draft.officeHours.trim(),
      contact_email: draft.contactEmail.trim() || null,
      contact_phone: draft.contactPhone.trim() || null,
      supported_insurance_categories: categoriesFromDraft(
        draft.supportedInsuranceCategories,
      ),
      escalation_message: draft.escalationMessage.trim(),
      expected_row_version: expectedRowVersion,
    }),
  });
  const body: unknown = await readJson(response);
  if (!response.ok) {
    throw apiError(response, body);
  }
  return parseReceptionistSettings(body);
}

export function parseReceptionistSettings(body: unknown): ReceptionistSettings {
  if (!isRecord(body)) {
    throw invalidResponse();
  }
  const categories = body.supported_insurance_categories;
  if (
    !Array.isArray(categories) ||
    categories.length === 0 ||
    !categories.every((category) => requiredString(category) !== undefined)
  ) {
    throw invalidResponse();
  }
  const id = requiredString(body.id);
  const agencyId = requiredString(body.agency_id);
  const publicName = requiredString(body.public_name);
  const greeting = requiredString(body.greeting);
  const officeHours = requiredString(body.office_hours);
  const escalationMessage = requiredString(body.escalation_message);
  const createdAt = requiredString(body.created_at);
  const updatedAt = requiredString(body.updated_at);
  if (
    id === undefined ||
    agencyId === undefined ||
    publicName === undefined ||
    greeting === undefined ||
    officeHours === undefined ||
    escalationMessage === undefined ||
    createdAt === undefined ||
    updatedAt === undefined ||
    typeof body.row_version !== "number" ||
    !nullableString(body.contact_email) ||
    !nullableString(body.contact_phone)
  ) {
    throw invalidResponse();
  }
  return {
    id,
    agencyId,
    publicName,
    greeting,
    officeHours,
    contactEmail: body.contact_email,
    contactPhone: body.contact_phone,
    supportedInsuranceCategories: categories as string[],
    escalationMessage,
    rowVersion: body.row_version,
    createdAt,
    updatedAt,
  };
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function apiError(
  response: Response,
  body: unknown,
): ReceptionistSettingsApiError {
  const error = isRecord(body) && isRecord(body.error) ? body.error : undefined;
  const message =
    error === undefined ? undefined : requiredString(error.message);
  return new ReceptionistSettingsApiError(
    response.status,
    message ?? "The receptionist settings request could not be completed",
  );
}

function invalidResponse(): ReceptionistSettingsApiError {
  return new ReceptionistSettingsApiError(
    502,
    "The receptionist settings service returned invalid data",
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requiredString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}
