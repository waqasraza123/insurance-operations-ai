from uuid import uuid4

from insurance_operations.approved_faqs.service import (
    faq_match_score,
    normalize_faq_question,
    select_faq_match,
)
from insurance_operations.database.models.approved_faq import AgencyApprovedFaq


def faq(question: str) -> AgencyApprovedFaq:
    return AgencyApprovedFaq(id=uuid4(), question=question)


def test_normalization_and_matching_are_deterministic() -> None:
    office_hours = faq("What are your office hours?")

    assert normalize_faq_question("  OFFICE—Hours?! ") == "office hours"
    assert (
        faq_match_score(
            "Please tell me your office hours",
            office_hours.question,
        )
        >= 0.8
    )
    assert (
        select_faq_match(
            "Please tell me your office hours",
            [office_hours],
        )
        is office_hours
    )


def test_matching_rejects_weak_and_ambiguous_questions() -> None:
    auto = faq("What auto insurance options do you support?")
    home = faq("What home insurance options do you support?")

    assert select_faq_match("Can you recommend coverage?", [auto, home]) is None
    assert (
        select_faq_match(
            "What insurance options do you support?",
            [auto, home],
        )
        is None
    )
