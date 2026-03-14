"""Minimal tests for prospectus_parser and capitalization_parser.

Each test uses the exact sentence style found in real SEC filings so
that regressions are caught if patterns are changed.
"""

from app.parsers.prospectus_parser import (
    extract_bookrunners,
    extract_greenshoe_shares,
    extract_offer_price,
    extract_price_range,
    extract_shares_offered_total,
    extract_shares_primary_secondary,
)
from app.parsers.capitalization_parser import (
    extract_fully_diluted_shares,
    extract_shares_outstanding_post_ipo,
    extract_shares_outstanding_pre_ipo,
)


# ── offer_price ───────────────────────────────────────────────────────────────

def test_offer_price_424b4_style():
    text = (
        "The initial public offering price per share of our Class A common stock is $34.00. "
        "We have been approved to list our Class A common stock on the NYSE."
    )
    assert extract_offer_price(text) == 34.0


def test_offer_price_price_to_public():
    text = "Price to the public $18.00 per share."
    assert extract_offer_price(text) == 18.0


def test_offer_price_none_when_absent():
    assert extract_offer_price("No price information here.") is None


# ── price_range ───────────────────────────────────────────────────────────────

def test_price_range_typical():
    text = "We expect an initial public offering price between $25.00 to $31.50 per share."
    low, high = extract_price_range(text)
    assert low == 25.0
    assert high == 31.50


def test_price_range_between_and():
    text = "The estimated price range is between $14.00 and $16.00."
    low, high = extract_price_range(text)
    assert low == 14.0
    assert high == 16.0


def test_price_range_none_when_absent():
    assert extract_price_range("No range here.") == (None, None)


# ── shares_offered_total ──────────────────────────────────────────────────────

def test_shares_offered_total_cover_page():
    text = (
        "Reddit, Inc. is offering 15,276,527 shares of its Class A common stock "
        "and the selling stockholders are offering 6,723,473 shares."
    )
    result = extract_shares_offered_total(text)
    assert result == 15_276_527.0


def test_shares_offered_total_none():
    assert extract_shares_offered_total("No share information.") is None


# ── shares_primary_secondary ──────────────────────────────────────────────────

def test_shares_primary_secondary():
    text = (
        "Reddit, Inc. is offering 15,276,527 shares of its Class A common stock "
        "and the selling stockholders identified in this prospectus are offering "
        "an aggregate of 6,723,473 shares of Class A common stock."
    )
    primary, secondary = extract_shares_primary_secondary(text)
    assert primary == 15_276_527.0
    assert secondary == 6_723_473.0


# ── greenshoe ─────────────────────────────────────────────────────────────────

def test_greenshoe_cover_page_style():
    text = (
        "We have granted the underwriters an option to purchase 3,300,000 shares "
        "of our Class A common stock from us to cover over-allotment options."
    )
    assert extract_greenshoe_shares(text) == 3_300_000.0


def test_greenshoe_option_style():
    text = (
        "The underwriters have an over-allotment option to purchase up to "
        "1,500,000 additional shares at the offering price."
    )
    assert extract_greenshoe_shares(text) == 1_500_000.0


def test_greenshoe_none():
    assert extract_greenshoe_shares("No greenshoe mentioned.") is None


# ── bookrunners ───────────────────────────────────────────────────────────────

def test_bookrunners_cover_page():
    text = (
        "The underwriters expect to deliver the shares against payment on March 25, 2024.\n"
        "MORGAN STANLEY\n"
        "GOLDMAN SACHS & CO. LLC\n"
        "J.P. MORGAN\n"
        "BOFA SECURITIES\n"
        "Prospectus dated March 20, 2024\n"
    )
    result = extract_bookrunners(text)
    assert result is not None
    assert "MORGAN STANLEY" in result
    assert "GOLDMAN SACHS & CO. LLC" in result
    assert "J.P. MORGAN" in result


# ── shares_outstanding_post_ipo ───────────────────────────────────────────────

def test_shares_outstanding_post_ipo_multi_class():
    text = (
        "Class A, Class B, and Class C common stock to be outstanding "
        "immediately after this offering\n"
        "158,993,090 shares (or 162,293,090 shares if the underwriters "
        "exercise their over-allotment option in full)\n"
    )
    result = extract_shares_outstanding_post_ipo(text)
    assert result == 158_993_090.0


def test_shares_outstanding_post_ipo_simple():
    text = (
        "We will have 50,000,000 shares of our common stock outstanding "
        "immediately after this offering."
    )
    result = extract_shares_outstanding_post_ipo(text)
    assert result == 50_000_000.0


def test_shares_outstanding_post_ipo_none():
    assert extract_shares_outstanding_post_ipo("No share count here.") is None


# ── shares_outstanding_pre_ipo ────────────────────────────────────────────────

def test_shares_outstanding_pre_ipo():
    text = (
        "The number is based on 143,716,563 shares of our common stock "
        "outstanding as of December 31, 2023."
    )
    result = extract_shares_outstanding_pre_ipo(text)
    assert result == 143_716_563.0


# ── fully_diluted_shares ──────────────────────────────────────────────────────

def test_fully_diluted_shares():
    text = (
        "We will have 175,000,000 shares of our common stock outstanding "
        "on a fully diluted basis immediately after this offering."
    )
    result = extract_fully_diluted_shares(text)
    assert result == 175_000_000.0
