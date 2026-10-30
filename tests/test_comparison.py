from finn.comparison import ComparisonDraft, comparison_valid


def make_draft(left="early", right="late"):
    return ComparisonDraft(
        answerable=True,
        earlier={
            "statement": "Management planned a capacity expansion.",
            "evidence_id": left,
            "quote": "We plan a capacity expansion in the next quarter.",
        },
        later={
            "statement": "Management reported commissioning the expansion.",
            "evidence_id": right,
            "quote": "The planned capacity expansion was commissioned this quarter.",
        },
        verdict="supported",
        basis="operational_milestone",
        assessment="Later commentary reports completion of the earlier operational plan.",
    )


def sources():
    return [
        {
            "chunk_id": "early",
            "document_id": "doc1",
            "discovery_label": "Jul 2026",
            "body": "We plan a capacity expansion in the next quarter.",
        },
        {
            "chunk_id": "late",
            "document_id": "doc2",
            "discovery_label": "Oct 2026",
            "body": "The planned capacity expansion was commissioned this quarter.",
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
    wrong[0]["discovery_label"] = "Dec 2026"
    assert not comparison_valid(make_draft(), wrong)
    wrong[0]["discovery_label"] = "Unverified label"
    assert not comparison_valid(make_draft(), wrong)


def test_comparison_rejects_new_numbers_not_in_quotes():
    bad = make_draft()
    bad.earlier.statement = "Management planned INR 500 crore of expansion."
    assert not comparison_valid(bad, sources())
