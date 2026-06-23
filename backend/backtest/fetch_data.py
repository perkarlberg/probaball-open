"""Download the historical international-results dataset used by the backtest.

  python3 -m backtest.fetch_data

Source: github.com/martj42/international_results (CC0). ~49k matches, 1872->,
with scores, tournament and neutral-venue flag. The CSV is gitignored; run this
to (re)populate backtest/data/results.csv.
"""
import os
import urllib.request

URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
DEST = os.path.join(os.path.dirname(__file__), "data", "results.csv")


def main():
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    print(f"downloading {URL}")
    urllib.request.urlretrieve(URL, DEST)
    with open(DEST, encoding="utf-8") as f:
        n = sum(1 for _ in f) - 1
    print(f"saved {DEST} ({n} matches)")


if __name__ == "__main__":
    main()
