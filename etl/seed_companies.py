#!/usr/bin/env python3
from pathlib import Path
import sys, time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(project_root))
load_dotenv(project_root / ".env")

from etl.config import Session
from backend.models import Company

from sqlalchemy.dialects.postgresql import insert as pg_insert  # Postgres upsert

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

def get_with_retries(url, headers, timeout=15, attempts=3):
    last = None
    for i in range(attempts):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code in (403, 429) and i < attempts - 1:
                time.sleep(2 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            if i < attempts - 1:
                time.sleep(2 * (i + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")

def fetch_sp500_companies() -> list[tuple[str, str]]:
    """Return list of (ticker, name)."""
    resp = get_with_retries(WIKI_URL, HEADERS, timeout=15, attempts=3)
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
    t0 = time.time()
    print("Fetching S&P 500 list...")
    companies = fetch_sp500_companies()
    print(f"Fetched {len(companies)} companies in {time.time() - t0:.2f}s")

    session = Session()
    try:
        # Bulk UPSERT in one statement: INSERT ... ON CONFLICT DO NOTHING
        rows = [{"ticker": t, "name": n} for t, n in companies]
        stmt = pg_insert(Company).values(rows).on_conflict_do_nothing(index_elements=["ticker"])
        result = session.execute(stmt)  # rowcount counts rows actually inserted
        session.commit()
        print(f"✅ Seeded {result.rowcount or 0} new companies (out of {len(companies)}).")
    finally:
        session.close()

if __name__ == "__main__":
    main()
