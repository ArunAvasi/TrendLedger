#!/usr/bin/env python3
"""
Fetch CompanySnapshot metrics using **free** data sources only:
  • **Finnhub** – core valuation & profitability ratios (requires FINNHUB_API_KEY in .env)
  • **yfinance** – balance-sheet rows & dividend dates (no key)
  • **Financial Modeling Prep** – fallback for metrics Finnhub omits, e.g. EV/EBITDA, price-to-book, forward P/E, cash & debt (requires FMP_API_KEY in .env, free tier ≤250 calls/day)

Returns a dict containing **exactly** the fields defined in backend.models.CompanySnapshot.

Run for a quick test:
    python etl/sources/snapshot.py  # defaults to ticker AAPL
"""
from __future__ import annotations

import os, sys, requests, yfinance as yf
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Environment & constants
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(project_root))
load_dotenv(project_root / ".env")

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_URL = "https://finnhub.io/api/v1"

FMP_KEY = os.getenv("FMP_API_KEY")
FMP_URL = "https://financialmodelingprep.com/api/v3"

# ---------------------------------------------------------------------------
# Helpers for each provider
# ---------------------------------------------------------------------------

def _finnhub_metric(ticker: str) -> Dict[str, Any]:
    if not FINNHUB_KEY:
        return {}
    try:
        r = requests.get(
            f"{FINNHUB_URL}/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": FINNHUB_KEY},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("metric", {})
    except Exception as e:
        print(f"Finnhub API error: {e}")
        return {}


def _fmp_endpoint(path: str, params: Dict[str, Any] | None = None) -> Any:
    if not FMP_KEY:
        print("FMP_KEY is not set")
        return None
    q = {"apikey": FMP_KEY, **(params or {})}
    try:
        url = f"{FMP_URL}/{path}"
        r = requests.get(url, params=q, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        print(f"FMP API error: {e}")
        return None


def _fmp_key_metrics(ticker: str) -> Dict[str, Any]:
    data = _fmp_endpoint(f"key-metrics-ttm/{ticker}")
    return data[0] if isinstance(data, list) and data else {}


def _fmp_balance_sheet(ticker: str) -> Dict[str, Any]:
    data = _fmp_endpoint(f"balance-sheet-statement/{ticker}", {"limit": 1})
    return data[0] if isinstance(data, list) and data else {}


def _yfinance_balance_dividend(ticker: str) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "cash": None,
        "debt": None,
        "net_cash": None,
        "ex_div_date": None,
        "payout_date": None,
    }
    try:
        yf_tkr = yf.Ticker(ticker)
        bs = yf_tkr.balance_sheet
        if not bs.empty:
            for lbl in ("Cash And Cash Equivalents", "Total Cash", "Cash"):
                if lbl in bs.index:
                    res["cash"] = int(bs.loc[lbl].iloc[0])
                    break
            for lbl in ("Long Term Debt", "Total Debt"):
                if lbl in bs.index:
                    res["debt"] = int(bs.loc[lbl].iloc[0])
                    break
            if res["cash"] is not None and res["debt"] is not None:
                res["net_cash"] = res["cash"] - res["debt"]
        # dividends
        divs = yf_tkr.dividends
        if not divs.empty:
            ex = divs.index[-1]
            res["ex_div_date"] = ex.date() if hasattr(ex, "date") else None
            res["payout_date"] = res["ex_div_date"]
    except Exception as e:
        print(f"yfinance error: {e}")
    return res

# ---------------------------------------------------------------------------
# Main fetch routine
# ---------------------------------------------------------------------------

def fetch_snapshot(ticker: str) -> Dict[str, Any]:
    finnhub = _finnhub_metric(ticker)
    yfin    = _yfinance_balance_dividend(ticker)
    fmp_km  = _fmp_key_metrics(ticker)
    fmp_bs  = _fmp_balance_sheet(ticker)

    # Value metrics
    market_cap     = finnhub.get("marketCapitalization") or fmp_km.get("marketCapTTM")
    pe_ttm         = finnhub.get("peTTM") or fmp_km.get("peRatioTTM")
    
    # Get earnings and revenue growth first since they're used for forward P/E estimation
    earnings_yoy = finnhub.get("epsGrowthQuarterlyYoy") or fmp_km.get("epsGrowthQuarterlyYoy")
    revenue_yoy  = finnhub.get("revenueGrowthQuarterlyYoy") or fmp_km.get("revenueGrowthQuarterlyYOY")
    
    # Forward P/E ratio - try multiple sources
    pe_fwd = (
        finnhub.get("forwardPE") or 
        fmp_km.get("forwardPE")
    )
    
    # If forward P/E is not available, we can estimate it based on current P/E and growth rates
    if pe_fwd is None and pe_ttm is not None and earnings_yoy is not None and earnings_yoy > 0:
        # Simple estimate: current P/E adjusted for growth
        estimated_growth = 1 + (earnings_yoy / 100)
        pe_fwd = pe_ttm / estimated_growth
    
    price_to_sales = finnhub.get("psTTM") or fmp_km.get("priceToSalesRatioTTM")
    
    # EV/EBITDA - FMP provides this directly as enterpriseValueOverEBITDATTM
    ev_to_ebitda = (
        fmp_km.get("enterpriseValueOverEBITDATTM") or
        (
            (finnhub.get("enterpriseValue") or fmp_km.get("enterpriseValueTTM")) and
            (finnhub.get("ebitdaTTM") or fmp_km.get("ebitdaTTM")) and
            (finnhub.get("enterpriseValue") or fmp_km.get("enterpriseValueTTM")) /
            (finnhub.get("ebitdaTTM") or fmp_km.get("ebitdaTTM"))
        )
    )
    
    # Price to Book ratio - try multiple sources
    price_to_book = (
        finnhub.get("pbTTM") or 
        fmp_km.get("priceToBookRatioTTM") or 
        fmp_km.get("pbRatioTTM") or 
        fmp_km.get("ptbRatioTTM")
    )
    
    fcf_yield = finnhub.get("currentEv/freeCashFlowTTM") or fmp_km.get("freeCashFlowYieldTTM")

    # Margins & growth
    profit_margin        = finnhub.get("netProfitMarginTTM") or fmp_km.get("netProfitMarginTTM")
    operating_margin_ttm = finnhub.get("operatingMarginTTM") or fmp_km.get("operatingMarginTTM")
    
    # Already calculated these above
    # earnings_yoy         = finnhub.get("epsGrowthQuarterlyYoy") or fmp_km.get("epsGrowthQuarterlyYoy")
    # revenue_yoy          = finnhub.get("revenueGrowthQuarterlyYoy") or fmp_km.get("revenueGrowthQuarterlyYOY")

    # Balance
    cash     = yfin["cash"]  or fmp_bs.get("cashAndCashEquivalents")
    debt     = yfin["debt"]  or fmp_bs.get("totalDebt")
    net_cash = yfin["net_cash"]
    if net_cash is None and (cash is not None and debt is not None):
        net_cash = cash - debt

    # Dividend
    dividend_yield = finnhub.get("dividendYieldIndicatedAnnual") or fmp_km.get("dividendYieldTTM")
    payout_ratio   = finnhub.get("payoutRatioTTM") or fmp_km.get("payoutRatioTTM")
    ex_div_date    = yfin["ex_div_date"]
    payout_date    = yfin["payout_date"]

    return {
        "market_cap": market_cap,
        "pe_ttm":     pe_ttm,
        "pe_fwd":     pe_fwd,
        "price_to_sales":  price_to_sales,
        "ev_to_ebitda":    ev_to_ebitda,
        "price_to_book":   price_to_book,
        "fcf_yield":       fcf_yield,
        "profit_margin":        profit_margin,
        "operating_margin_ttm": operating_margin_ttm,
        "earnings_yoy":         earnings_yoy,
        "revenue_yoy":          revenue_yoy,
        "cash":      cash,
        "debt":      debt,
        "net_cash":  net_cash,
        "dividend_yield": dividend_yield,
        "payout_ratio":   payout_ratio,
        "ex_div_date":    ex_div_date,
        "payout_date":    payout_date,
    }


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pprint, argparse

    parser = argparse.ArgumentParser(description="Fetch snapshot for ticker")
    parser.add_argument("ticker", nargs="?", default="AAPL")
    args = parser.parse_args()

    pprint.pprint(fetch_snapshot(args.ticker.upper()))