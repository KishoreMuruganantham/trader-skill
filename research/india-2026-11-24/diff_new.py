"""Diff the Nifty 500 screen against the investor's own 35 name watchlist.

Shows which objectively screened names are NEW to the investor, grouped by
industry, so the shortlist for deeper research is clean.
"""

import csv, json, os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(BASE, "trader")

owned = set()
rows = json.load(open(os.path.join(T, "analysis_rows.json"), encoding="utf-8"))
for r in rows:
    owned.add(r["ticker"])

nifty = list(csv.DictReader(open(os.path.join(T, "nifty500_metrics.csv"), encoding="utf-8")))
print("Nifty 500 rows: %d | investor's own list: %d" % (len(nifty), len(owned)))


def f(v):
    try:
        return float(v)
    except Exception:
        return None


new = [r for r in nifty if r["ticker"] not in owned and r["ticker"]]
print("new names not on the investor's list: %d" % len(new))

budget = 3500.0
by_ind = defaultdict(list)
for r in new:
    p = f(r["price"])
    roe = f(r["roe"])
    pe = f(r["pe"])
    pm = f(r["operating_margin"])
    if p is None or p > budget:
        continue
    by_ind[r["industry"]].append(r)

print("\n=== new names, affordable at one share (price <= Rs %.0f) ===" % budget)
for ind in sorted(by_ind, key=lambda i: -len(by_ind[i])):
    names = by_ind[ind]
    print("\n%s (%d affordable)" % (ind, len(names)))
    for r in sorted(names, key=lambda x: -(f(x["roe"]) or 0)):
        roe = f(r["roe"])
        pe = f(r["pe"])
        pm = f(r["operating_margin"])
        print("   %-16s Rs %8.2f  PE %-7s ROE %-7s opmgn %-8s %s" % (
            r["ticker"], f(r["price"]), round(pe, 1) if pe else "n/a",
            round(roe * 100, 1) if roe else "n/a", round(pm * 100, 1) if pm else "n/a",
            (r["name"] or "")[:30]))

# Sectors the investor never covered at all
covered = defaultdict(set)
for r in rows:
    covered[r["group"]].add(r["ticker"])
print("\n=== the investor's groups ===")
for g, t in covered.items():
    print("   %-12s %d names" % (g, len(t)))
