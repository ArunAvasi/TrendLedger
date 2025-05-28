#!/usr/bin/env python3
"""
Seed the `companies` table with the current S&P 500 list
by scraping Wikipedia, so no API key is needed.
"""

from pathlib import Path
import sys
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# allow imports from project root
project_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(project_root))

# load .env for DB creds
load_dotenv(project_root / ".env")

from etl.config     import Session
from backend.models import Company

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

def fetch_sp500_tickers() -> list[str]:
    """Scrape Wikipedia’s table and return a list of ticker symbols."""
    resp = requests.get(WIKI_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # The table has id="constituents"
    table = soup.find("table", {"id": "constituents"})
    if not table:
        raise RuntimeError("Could not find the S&P 500 table on Wikipedia")

    tickers = []
    # First <td> of each <tr> in <tbody> is the ticker
    for row in table.tbody.find_all("tr"):
        cols = row.find_all("td")
        if cols:
            ticker = cols[0].get_text(strip=True)
            # Wikipedia uses periods in tickers like BRK.B → convert to BRK-B
            ticker = ticker.replace(".", "-")
            tickers.append(ticker)
    return tickers

def main():
    tickers = fetch_sp500_tickers()
    session = Session()
    added = 0

    for t in tickers:
        if not session.query(Company).filter_by(ticker=t).first():
            session.add(Company(ticker=t))
            added += 1

    session.commit()
    session.close()

    print(f"✅ Seeded {added} new companies (out of {len(tickers)}).")

if __name__ == "__main__":
    main()