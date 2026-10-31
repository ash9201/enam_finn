from finn.comparison import ComparisonDraft, comparison_valid


def make_draft(left="early", right="late"):
    return ComparisonDraft(
        answerable=True,
        earlier={
            "statement": "Management planned a capacity expansion.",
            "evidence_id": left,
            "quote": "We plan a new manufacturing capacity expansion at our plant in the next quarter.",
        },
        later={
            "statement": "Management reported commissioning the expansion.",
            "evidence_id": right,
            "quote": "The planned manufacturing capacity expansion at our new plant was commissioned this quarter.",
        },
        verdict="delivered",
        basis="operational_milestone",
        assessment="Later commentary reports completion of the earlier operational plan.",
    )


def sources():
    return [
        {
            "chunk_id": "early",
            "document_id": "doc1",
            "discovery_label": "Jul 2026",
            "body": "We plan a new manufacturing capacity expansion at our plant in the next quarter.",
            "document_date": "2026-07-28",
            "management_spans": [
                {
                    "text": "We plan a new manufacturing capacity expansion at our plant in the next quarter.",
                    "speaker": {"name": "CEO", "role": "CEO"},
                }
            ],
        },
        {
            "chunk_id": "late",
            "document_id": "doc2",
            "discovery_label": "Oct 2026",
            "body": "The planned manufacturing capacity expansion at our new plant was commissioned this quarter.",
            "document_date": "2026-10-16",
            "management_spans": [
                {
                    "text": "The planned manufacturing capacity expansion at our new plant was commissioned this quarter.",
                    "speaker": {"name": "CEO", "role": "CEO"},
                }
            ],
        },
    ]


def test_comparison_requires_two_calls_and_exact_quotes():
    assert comparison_valid(make_draft(), sources())
    assert not comparison_valid(make_draft(right="early"), sources())
    bad = make_draft()
    bad.later.quote = "A made-up outcome that is not in the source."
    assert not comparison_valid(bad, sources())


def test_comparison_rejects_reversed_or_unknown_chronology():
    wrong = sources()
    wrong[0]["document_date"] = "2026-12-01"
    assert not comparison_valid(make_draft(), wrong)
    wrong[0]["document_date"] = "Unverified date"
    assert not comparison_valid(make_draft(), wrong)


def test_comparison_rejects_new_numbers_not_in_quotes():
    bad = make_draft()
    bad.earlier.statement = "Management planned INR 500 crore of expansion."
    assert not comparison_valid(bad, sources())


def test_an_analyst_question_cannot_be_used_as_management_evidence():
    items = sources()
    items[1]["management_spans"] = []
    assert not comparison_valid(make_draft(), items)


def test_a_fragment_or_same_call_does_not_make_a_meaningful_pair():
    draft = make_draft()
    draft.earlier.quote = "this is what we had talked about FY27"
    assert not comparison_valid(draft, sources())
    items = sources()
    items[0]["document_date"] = items[1]["document_date"]
    assert not comparison_valid(make_draft(), items)
