"""Build the final shortlist of NEW names from the Nifty 500 screen.

Scores each new name on a Buffett style composite, checks that one or two
shares actually fit the budget, and writes a compact brief for the analyst.
"""

import csv, json, os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(BASE, "trader")
BUDGET = 3500.0

owned = {r["ticker"] for r in json.load(open(os.path.join(T, "analysis_rows.json"), encoding="utf-8"))}


def f(v):
    try:
        return float(v)
    except Exception:
        return None


rows = list(csv.DictReader(open(os.path.join(T, "nifty500_metrics.csv"), encoding="utf-8")))


FINANCIAL = ("financial services", "insurance", "asset management")


def is_financial(r):
    ind = (r["industry"] or "").lower()
    return any(k in ind for k in FINANCIAL)


def score(r):
    """Buffett style composite. Returns None if the name fails a basic gate."""
    p, roe, pe = f(r["price"]), f(r["roe"]), f(r["pe"])
    pm, pb, eg = f(r["operating_margin"]), f(r["price_to_book"]), f(r["earnings_growth"])
    rg, dy = f(r["revenue_growth"]), f(r["dividend_yield"])
    fin = is_financial(r)
    if p is None or p > BUDGET or roe is None or roe < 0.15:
        return None
    # Operating margin and price to book are not comparable for banks, insurers
    # and asset managers, so they are not used to gate those names.
    if not fin and pm is not None and pm < 0.10:
        return None
    if pe is None or pe < 5 or pe > 40:
        return None
    if not fin and pb is not None and pb > 6:
        return None
    s = 0.0
    s += min(roe / 0.35, 1.0) * 35                       # returns
    s += min((pe and (35 - pe) / 30) or 0, 1.0) * 25      # valuation, cheaper is better
    s += min((pm or 0) / 0.30, 1.0) * 15                  # margin power
    if pb is not None and roe:
        s += min(max(0.0, (roe - pb / 100)) / 0.20, 1.0) * 10   # ROE against price to book
    if eg is not None:
        s += max(-0.2, min(eg, 1.0)) * 10                 # earnings direction
    if rg is not None:
        s += max(-0.1, min(rg, 0.5)) * 5                  # revenue direction
    if dy:
        s += min(dy / 0.03, 1.0) * 5                     # dividend
    return round(s, 1)


cands = []
for r in rows:
    if r["ticker"] in owned:
        continue
    sc = score(r)
    if sc is None:
        continue
    p = f(r["price"])
    cands.append({
        "ticker": r["ticker"], "name": r["name"], "industry": r["industry"],
        "price": p, "pe": f(r["pe"]), "roe": f(r["roe"]), "pb": f(r["price_to_book"]),
        "opm": f(r["operating_margin"]), "revg": f(r["revenue_growth"]),
        "earng": f(r["earnings_growth"]), "divy": f(r["dividend_yield"]),
        "yr_low": f(r["yr_low"]), "yr_high": f(r["yr_high"]),
        "target": f(r["analyst_target"]), "n_analysts": f(r["analyst_count"]),
        "score": sc,
        "shares_fit_1": p <= BUDGET,
        "shares_fit_2": p * 2 <= BUDGET,
        "pct_of_52w": round((p - f(r["yr_low"])) / (f(r["yr_high"]) - f(r["yr_low"])) * 100, 1)
        if f(r["yr_low"]) and f(r["yr_high"]) and f(r["yr_high"]) > f(r["yr_low"]) else None,
    })

cands.sort(key=lambda x: -x["score"])
print("new names passing the gate: %d" % len(cands))
print("\n%-16s %9s %6s %7s %6s %6s %6s %5s %6s %s" % (
    "ticker", "price", "score", "PE", "ROE%", "P/B", "opm%", "2sh?", "52w%", "name"))
for c in cands[:45]:
    print("%-16s %9.2f %6.1f %7s %6s %6s %6s %5s %6s %s" % (
        c["ticker"], c["price"], c["score"],
        round(c["pe"], 1) if c["pe"] else "n/a",
        round(c["roe"] * 100, 1) if c["roe"] else "n/a",
        round(c["pb"], 1) if c["pb"] else "n/a",
        round(c["opm"] * 100, 1) if c["opm"] else "n/a",
        "yes" if c["shares_fit_2"] else "no",
        c["pct_of_52w"], (c["name"] or "")[:28]))

json.dump(cands, open(os.path.join(T, "new_candidates.json"), "w", encoding="utf-8"), indent=2)

by_ind = defaultdict(list)
for c in cands:
    by_ind[c["industry"]].append(c)
print("\n=== sectors, and how many new names each has in the top 45 ===")
for ind in sorted(by_ind, key=lambda i: -len(by_ind[i])):
    print("  %-28s %d" % (ind, len(by_ind[ind])))
