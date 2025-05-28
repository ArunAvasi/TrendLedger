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

def fetch_sp500_companies() -> list[tuple[str, str]]:
    """Scrape Wikipedia’s table and return a list of (ticker, company_name)."""
    resp = requests.get(WIKI_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", {"id": "constituents"})
    if not table:
        raise RuntimeError("Could not find the S&P 500 table on Wikipedia")

    results: list[tuple[str, str]] = []
    for row in table.tbody.find_all("tr"):
        cols = row.find_all("td")
        if cols:
            ticker = cols[0].get_text(strip=True).replace(".", "-")
            name = cols[1].get_text(strip=True)
            results.append((ticker, name))
    return results

def main():
    companies = fetch_sp500_companies()
    session = Session()
    added = 0

    for ticker, name in companies:
        exists = session.query(Company).filter_by(ticker=ticker).first()
        if not exists:
            session.add(Company(ticker=ticker, name=name))
            added += 1

    session.commit()
    session.close()

    print(f"✅ Seeded {added} new companies (out of {len(companies)}).")

if __name__ == "__main__":
    main()
