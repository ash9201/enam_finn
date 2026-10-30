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
        (
            "Schedule of meet for 2QFY27 Earnings Discussion |SUBJECT: Analysts/Institutional Investor Meet/Con. Call Updates",
            "investor_meeting",
            0,
        ),
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


def price_fixture(
    monkeypatch, split_index=None, failures=0, missing_latest=False, missing_history=False
):
    import yfinance
    from yfinance.exceptions import YFRateLimitError

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
    if missing_latest:
        frame.iloc[-1, frame.columns.get_loc("Close")] = float("nan")
    if missing_history:
        frame.iloc[-5, frame.columns.get_loc("Close")] = float("nan")

    class Ticker:
        attempts = 0

        def history(self, **kwargs):
            self.attempts += 1
            if self.attempts <= failures:
                raise YFRateLimitError()
            return frame

    monkeypatch.setattr(yfinance, "Ticker", lambda symbol: Ticker())
    return price_probe({"symbol": "TEST"})


def test_incomplete_latest_bar_uses_exact_dated_primary_close_and_volume(monkeypatch):
    calls = []

    def primary(client, session, company):
        calls.append((session, company["symbol"]))
        return {
            "close": 106,
            "volume": 400,
            "previous_close": 100,
            "source_url": "https://nsearchives.nseindia.com/test.zip",
        }

    monkeypatch.setattr("finn.sources.exchange_session_bar", primary)
    result = price_fixture(monkeypatch, missing_latest=True)
    assert calls == [("2026-02-04", "TEST")]
    assert result["last_session"] == "2026-02-04"
    assert result["close"] == 106
    assert result["volume_ratio"] == 4
    assert result["price_change_pct"] == pytest.approx(6)
    assert "NSE" in result["provider"]
    assert result["source_url"].endswith("test.zip")


def test_incomplete_latest_bar_cannot_silently_drop_to_an_older_session(monkeypatch):
    def unavailable(*args):
        raise ValueError("NSE archive unavailable")

    monkeypatch.setattr("finn.sources.exchange_session_bar", unavailable)
    with pytest.raises(ValueError, match="NSE archive unavailable"):
        price_fixture(monkeypatch, missing_latest=True)


def test_missing_baseline_session_is_not_silently_skipped(monkeypatch):
    with pytest.raises(ValueError, match="20-session baseline"):
        price_fixture(monkeypatch, missing_history=True)


def test_one_rate_limit_recovers_with_a_bounded_retry(monkeypatch):
    waits = []
    monkeypatch.setattr("finn.sources.time.sleep", waits.append)
    result = price_fixture(monkeypatch, failures=1)
    assert waits == [5]
    assert result["history_fetch_attempts"] == 2
    assert result["volume_ratio"] == 3


def test_persistent_rate_limit_is_not_replaced_with_an_old_or_invented_bar(monkeypatch):
    from yfinance.exceptions import YFRateLimitError

    waits = []
    monkeypatch.setattr("finn.sources.time.sleep", waits.append)
    with pytest.raises(YFRateLimitError):
        price_fixture(monkeypatch, failures=2)
    assert waits == [5]


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
