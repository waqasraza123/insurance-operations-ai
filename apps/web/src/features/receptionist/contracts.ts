export type ReceptionistSettings = Readonly<{
  id: string;
  agencyId: string;
  publicName: string;
  greeting: string;
  officeHours: string;
  contactEmail: string | null;
  contactPhone: string | null;
  supportedInsuranceCategories: readonly string[];
  escalationMessage: string;
  rowVersion: number;
  createdAt: string;
  updatedAt: string;
}>;

export type ReceptionistSettingsDraft = Readonly<{
  publicName: string;
  greeting: string;
  officeHours: string;
  contactEmail: string;
  contactPhone: string;
  supportedInsuranceCategories: string;
  escalationMessage: string;
}>;
