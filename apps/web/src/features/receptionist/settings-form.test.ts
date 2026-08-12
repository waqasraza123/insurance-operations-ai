import { describe, expect, it } from "vitest";

import type { ReceptionistSettingsDraft } from "./contracts";
import { categoriesFromDraft, validateSettingsDraft } from "./settings-form";

const VALID_DRAFT: ReceptionistSettingsDraft = {
  publicName: "Harborline Insurance",
  greeting: "Welcome to our synthetic receptionist.",
  officeHours: "Monday through Friday, 9 AM to 5 PM Eastern",
  contactEmail: "receptionist@example.com",
  contactPhone: "",
  supportedInsuranceCategories: "Auto\nHomeowners",
  escalationMessage: "A licensed team member will follow up.",
};

describe("receptionist settings form", () => {
  it("normalizes newline-delimited insurance categories", () => {
    expect(categoriesFromDraft(" Auto \n\nHomeowners\nRenters ")).toEqual([
      "Auto",
      "Homeowners",
      "Renters",
    ]);
  });

  it("requires a contact method and unique categories", () => {
    expect(
      validateSettingsDraft({
        ...VALID_DRAFT,
        contactEmail: "",
        contactPhone: "",
      }),
    ).toBe("Add a public email address or phone number.");
    expect(
      validateSettingsDraft({
        ...VALID_DRAFT,
        supportedInsuranceCategories: "Auto\nauto",
      }),
    ).toBe("Supported insurance categories must be unique.");
  });

  it("accepts a complete receptionist configuration", () => {
    expect(validateSettingsDraft(VALID_DRAFT)).toBeUndefined();
  });
});
