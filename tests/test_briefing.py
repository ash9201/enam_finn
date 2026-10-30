from datetime import datetime

import pandas as pd
import pytest

from finn.briefing import classify_filing
from finn.sources import parse_announcement_date, price_probe


@pytest.mark.parametrize(
    "text,category,priority",
    [
        ("Newspaper publication of financial results", "publication", 0),
        ("Intimation of board meeting to consider financial results", "meeting_notice", 1),
        ("Unaudited consolidated financial results for the quarter", "results", 3),
        ("Resignation of Chief Financial Officer", "management_change", 3),
        ("Appointment of Managing Director", "management_change", 3),
        ("Acquisition of subsidiary", "m_and_a", 3),
        ("Credit rating downgrade", "credit_rating", 3),
        ("Credit rating reaffirmed", "credit_rating", 1),
        ("Earnings call transcript", "earnings_call", 1),
        ("Investor meeting schedule", "investor_meeting", 0),
        ("ESOP allotment", "routine", 0),
        ("General updates with an unfamiliar disclosure", "unclassified", 2),
        ("Appointment of statutory auditor due to mandatory auditor rotation", "routine", 0),
        ("Commercial operation of a new power project", "business_update", 2),
    ],
)
def test_filing_priority_distinguishes_substance_from_notices(text, category, priority):
    result = classify_filing(text)
    assert result[:2] == (category, priority)
    assert result[2]


def test_exchange_timestamps_support_both_observed_formats():
    assert parse_announcement_date("30-OCT-2026 13:21") == "2026-10-30T13:21:00+05:30"
    assert parse_announcement_date("30-Oct-2026 13:21:43") == "2026-10-30T13:21:43+05:30"
    with pytest.raises(ValueError, match="no timestamp was invented"):
        parse_announcement_date("not a timestamp")


def price_fixture(monkeypatch, split_index=None):
    import yfinance

    frame = pd.DataFrame(
        {
            "Close": [100] * 24 + [105],
            "Volume": [9999] * 4 + [100] * 20 + [300],
            "Stock Splits": [0] * 25,
        },
        index=pd.date_range("2026-01-01", periods=25, freq="B", tz="Asia/Kolkata"),
    )
    if split_index is not None:
        frame.iloc[split_index, frame.columns.get_loc("Stock Splits")] = 2

    class Ticker:
        def history(self, **kwargs):
            return frame

    monkeypatch.setattr(yfinance, "Ticker", lambda symbol: Ticker())
    return price_probe({"symbol": "TEST"})


def test_volume_baseline_excludes_current_day_and_older_history(monkeypatch):
    result = price_fixture(monkeypatch)
    assert result["previous_20_mean_volume"] == 100
    assert result["volume_ratio"] == 3
    assert result["price_change_pct"] == pytest.approx(5)


def test_split_inside_baseline_suppresses_misleading_volume_alert(monkeypatch):
    result = price_fixture(monkeypatch, split_index=10)
    assert result["volume_ratio"] is None
    assert result["price_change_pct"] == pytest.approx(5)


def test_split_today_suppresses_price_and_volume_comparisons(monkeypatch):
    result = price_fixture(monkeypatch, split_index=24)
    assert result["price_change_pct"] is None
    assert result["volume_ratio"] is None
