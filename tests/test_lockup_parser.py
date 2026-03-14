"""Tests for app.parsers.lockup_parser."""

from __future__ import annotations

import pytest

from app.parsers.lockup_parser import (
    determine_confidence,
    detect_staged_unlock,
    extract_lockup_days,
    extract_unlock_notes,
)


# ── extract_lockup_days ───────────────────────────────────────────────────────

class TestExtractLockupDays:

    def test_standard_180_day_full_phrase(self):
        text = (
            "Lock-Up Agreements\n"
            "We have agreed not to offer or sell any shares of our common stock "
            "for a period of 180 days after the date of this prospectus without "
            "the prior written consent of the representatives."
        )
        assert extract_lockup_days(text) == 180

    def test_standard_180_day_short_phrase(self):
        text = (
            "Our executive officers and directors have agreed not to sell any "
            "common stock for 180 days after the date of this prospectus."
        )
        assert extract_lockup_days(text) == 180

    def test_standard_90_day(self):
        text = (
            "Lock-Up Agreements\n"
            "The Company has agreed, for a period of 90 days after the date of "
            "this prospectus, not to offer, sell, contract to sell or otherwise "
            "dispose of any shares of common stock."
        )
        assert extract_lockup_days(text) == 90

    def test_beginning_pattern(self):
        text = (
            "Shares Eligible for Future Sale\n"
            "Beginning 181 days after the date of this prospectus, holders of "
            "restricted shares may sell their shares in the open market."
        )
        assert extract_lockup_days(text) == 181

    def test_dash_pattern(self):
        text = (
            "We are subject to a 180-day lock-up period pursuant to our "
            "underwriting agreement."
        )
        assert extract_lockup_days(text) == 180

    def test_lockup_period_of_pattern(self):
        text = (
            "The underwriting agreement contains a lock-up period of 180 days "
            "beginning on the effective date."
        )
        assert extract_lockup_days(text) == 180

    def test_360_day(self):
        text = (
            "Directors have entered into lock-up agreements for a period of "
            "360 days after the date of this prospectus."
        )
        assert extract_lockup_days(text) == 360

    def test_returns_none_when_no_lockup(self):
        text = "This prospectus does not contain any lock-up information."
        assert extract_lockup_days(text) is None

    def test_ignores_out_of_bounds_days(self):
        # 5 days is below the 30-day sanity floor
        text = "We agreed not to sell shares for 5 days after the offering."
        assert extract_lockup_days(text) is None

    def test_most_frequent_value_wins(self):
        # 180 appears twice, 90 appears once → 180 wins
        text = (
            "Lock-Up Agreements\n"
            "Officers agreed not to sell for 180 days after this prospectus. "
            "Directors also agreed not to sell for 180 days after this prospectus. "
            "Certain holders agreed not to sell for 90 days after the offering."
        )
        assert extract_lockup_days(text) == 180


# ── detect_staged_unlock ──────────────────────────────────────────────────────

class TestDetectStagedUnlock:

    def test_percentage_released(self):
        text = (
            "Lock-Up Agreements\n"
            "25% of the shares will be released from the lock-up after 90 days."
        )
        assert detect_staged_unlock(text) is True

    def test_each_period_language(self):
        text = (
            "Shares Eligible for Future Sale\n"
            "At the beginning of each 180-day period, additional shares become "
            "available for sale."
        )
        assert detect_staged_unlock(text) is True

    def test_tranches_language(self):
        text = "The restricted shares will be released in tranches over 12 months."
        assert detect_staged_unlock(text) is True

    def test_pro_rata_language(self):
        text = "Shares will vest pro-rata over 24 months following the IPO."
        assert detect_staged_unlock(text) is True

    def test_standard_180_no_staged(self):
        text = (
            "Lock-Up Agreements\n"
            "We have agreed not to sell any shares for a period of 180 days "
            "after the date of this prospectus."
        )
        assert detect_staged_unlock(text) is False

    def test_empty_text_no_staged(self):
        assert detect_staged_unlock("") is False


# ── extract_unlock_notes ──────────────────────────────────────────────────────

class TestExtractUnlockNotes:

    def test_captures_lockup_sentence(self):
        text = (
            "Lock-Up Agreements\n"
            "We have agreed not to sell any shares of our common stock for a "
            "period of 180 days after the date of this prospectus."
        )
        notes = extract_unlock_notes(text)
        assert notes is not None
        assert "180" in notes

    def test_returns_none_when_no_lockup(self):
        text = "This prospectus contains only generic boilerplate."
        assert extract_unlock_notes(text) is None

    def test_notes_length_capped(self):
        long_text = (
            "Lock-Up Agreements\n"
            "For a period of 180 days after the date of this prospectus, we "
            "have agreed not to sell, offer, pledge, contract to sell, sell any "
            "option or contract to purchase, purchase any option or contract to "
            "sell, grant any option, right or warrant to purchase, lend or "
            "otherwise transfer or dispose of, directly or indirectly, any "
            "shares of common stock or any securities convertible or exchangeable "
            "into or exercisable for any shares of common stock. "
            * 3
        )
        notes = extract_unlock_notes(long_text)
        assert notes is None or len(notes) <= 300


# ── determine_confidence ──────────────────────────────────────────────────────

class TestDetermineConfidence:

    def test_high_for_standard_180_no_staged(self):
        text = "for 180 days after the date of this prospectus"
        assert determine_confidence(text, 180, False) == "high"

    def test_high_for_standard_90_no_staged(self):
        text = "for 90 days after the date of this prospectus"
        assert determine_confidence(text, 90, False) == "high"

    def test_medium_for_staged_unlock(self):
        text = "for 180 days; 25% released after 90 days"
        assert determine_confidence(text, 180, True) == "medium"

    def test_medium_for_unusual_days(self):
        text = "for 270 days after the offering"
        assert determine_confidence(text, 270, False) == "medium"

    def test_low_when_no_lockup_days(self):
        text = "no lock-up period mentioned"
        assert determine_confidence(text, None, False) == "low"

    def test_low_when_days_none_and_staged(self):
        assert determine_confidence("", None, True) == "low"

    def test_high_for_360_day_standard(self):
        assert determine_confidence("for 360 days", 360, False) == "high"
