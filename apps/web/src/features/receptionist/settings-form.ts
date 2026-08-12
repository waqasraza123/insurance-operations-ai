import type {
  ReceptionistSettings,
  ReceptionistSettingsDraft,
} from "./contracts";

export function settingsDraft(
  settings: ReceptionistSettings,
): ReceptionistSettingsDraft {
  return {
    publicName: settings.publicName,
    greeting: settings.greeting,
    officeHours: settings.officeHours,
    contactEmail: settings.contactEmail ?? "",
    contactPhone: settings.contactPhone ?? "",
    supportedInsuranceCategories:
      settings.supportedInsuranceCategories.join("\n"),
    escalationMessage: settings.escalationMessage,
  };
}

export function categoriesFromDraft(value: string): string[] {
  return value
    .split("\n")
    .map((category) => category.trim())
    .filter(Boolean);
}

export function validateSettingsDraft(
  draft: ReceptionistSettingsDraft,
): string | undefined {
  if (!draft.publicName.trim()) {
    return "Agency public name is required.";
  }
  if (!draft.greeting.trim()) {
    return "Greeting is required.";
  }
  if (!draft.officeHours.trim()) {
    return "Office hours are required.";
  }
  if (!draft.contactEmail.trim() && !draft.contactPhone.trim()) {
    return "Add a public email address or phone number.";
  }
  const categories = categoriesFromDraft(draft.supportedInsuranceCategories);
  if (categories.length === 0) {
    return "Add at least one supported insurance category.";
  }
  if (
    new Set(categories.map((category) => category.toLowerCase())).size !==
    categories.length
  ) {
    return "Supported insurance categories must be unique.";
  }
  if (!draft.escalationMessage.trim()) {
    return "Human escalation message is required.";
  }
  return undefined;
}
