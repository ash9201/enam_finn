import copy

import pytest
from finn.briefing import classify_filing
from finn.filing_reclassification import repair_ratings


@pytest.mark.parametrize(
    "text,priority,fragment",
    [
        ("Credit rating downgraded by ICRA", 3, "downgraded"),
        ("Credit ratings reaffirmed by CRISIL", 1, "reaffirmed"),
        ("Rating action: long-term rating upgraded", 2, "upgraded"),
        ("Rating assigned by Acuité to bank facilities", 1, "disclosure"),
        ("CARE Ratings reaffirmed long term bank facilities", 1, "reaffirmed"),
        ("India Ratings revised the outlook to negative", 3, "negative"),
        ("Fitch long-term issuer default rating affirmed", 1, "reaffirmed"),
        ("ICRA credit rating outlook revised from stable to negative", 3, "negative"),
        ("Credit rating outlook changed to positive", 2, "outlook"),
        ("Credit rating withdrawn", 2, "withdrawn"),
        ("Credit rating withdrawn following full redemption", 1, "withdrawn"),
        ("Infomerics has assigned long-term bank facilities", 1, "disclosure"),
    ],
)
def test_genuine_credit_actions_have_specific_priority(text, priority, fragment):
    category, p, reason = classify_filing(text)
    assert category == "credit_rating" and p == priority and fragment in reason.lower()


@pytest.mark.parametrize(
    "text",
    [
        "The operating profit improved and the company is generating cash.",
        "The factory is operating normally.",
        "Celebrating a new product launch.",
        "The team is collaborating on integrating a new generating unit.",
        "CARE Ratings published a report on operating trends in the industry.",
        "ICRA released an industry report about generating power.",
        "ESG rating upgraded by an independent provider.",
        "Buy rating upgraded by a stock analyst.",
        "Operating and financial update for the quarter.",
    ],
)
def test_incidental_substrings_and_non_credit_ratings_are_not_credit(text):
    assert classify_filing(text)[0] != "credit_rating"


def test_repair_is_idempotent_preserves_ids_sources_and_review_state():
    class Store:
        def __init__(self):
            self.records = [
                {
                    "id": "immutable-filing",
                    "symbol": "TEST",
                    "description": "The company is generating cash.",
                    "category": "credit_rating",
                    "priority": 1,
                    "review_reason": "old reason",
                    "source_url": "https://exchange.example/original.pdf",
                    "reviewed": True,
                },
                {
                    "id": "unrelated",
                    "symbol": "TEST",
                    "description": "Unaudited financial results",
                    "category": "results",
                    "priority": 3,
                    "review_reason": "keep",
                    "reviewed": False,
                },
            ]

        def rows(self, table, **filters):
            return [
                copy.deepcopy(r)
                for r in self.records
                if r["category"] in ["credit_rating", "unclassified"]
            ]

        def patch(self, table, values, **filters):
            row = next(r for r in self.records if filters["id"] == "eq." + r["id"])
            assert set(values) == {"category", "priority", "review_reason"}
            row.update(values)

    s = Store()
    original = copy.deepcopy(s.records)
    assert len(repair_ratings(s)["changes"]) == 1 and s.records == original
    assert len(repair_ratings(s, apply=True)["changes"]) == 1
    assert (
        s.records[0]["id"] == original[0]["id"]
        and s.records[0]["source_url"] == original[0]["source_url"]
        and s.records[0]["reviewed"]
    )
    assert s.records[1] == original[1]
    assert repair_ratings(s, apply=True)["changes"] == []
