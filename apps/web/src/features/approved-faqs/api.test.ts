import { describe, expect, it } from "vitest";

import { parseApprovedFaq, parseApprovedFaqLookup } from "./api";

describe("approved FAQ API parsing", () => {
  it("parses versioned FAQ and source-backed lookup responses", () => {
    const faq = parseApprovedFaq({
      id: "faq-1",
      agency_id: "agency-1",
      question: "What are your hours?",
      approved_answer: "Weekdays from 9 AM to 5 PM.",
      status: "ACTIVE",
      row_version: 3,
      created_at: "2026-08-08T00:00:00Z",
      updated_at: "2026-08-08T00:00:00Z",
    });
    const lookup = parseApprovedFaqLookup({
      matched: true,
      answer: faq.approvedAnswer,
      fallback_message: "A licensed team member will follow up.",
      source: {
        faq_id: faq.id,
        question: faq.question,
        row_version: faq.rowVersion,
      },
    });

    expect(faq.status).toBe("ACTIVE");
    expect(lookup.source?.faqId).toBe("faq-1");
    expect(lookup.answer).toBe("Weekdays from 9 AM to 5 PM.");
  });

  it("rejects a matched response without a source", () => {
    expect(() =>
      parseApprovedFaqLookup({
        matched: true,
        answer: "Unsupported answer",
        fallback_message: "Human follow-up required.",
        source: null,
      }),
    ).toThrow("invalid data");
  });
});
