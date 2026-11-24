import json, os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trader")
d = json.load(open(os.path.join(P, "fundamentals.json"), encoding="utf-8"))

seen = {}
rows = []
for label, r in d.items():
    if not r.get("resolved"):
        continue
    sym = r["symbol"]
    if sym in seen:
        continue
    seen[sym] = True
    f = r.get("fundamentals") or {}
    c = r.get("chart") or {}

    def n(v, d=4):
        return round(v, d) if isinstance(v, (int, float)) else None

    rows.append({
        "ticker": sym,
        "label": r["label"],
        "group": r["group"],
        "name": (c.get("name") or "")[:40],
        "price": n(c.get("price"), 2),
        "yr_low": n(c.get("yr_low"), 2),
        "yr_high": n(c.get("yr_high"), 2),
        "mcap_cr": n((f.get("marketCap") or 0) / 1e7) if f.get("marketCap") else None,
        "pe": n(f.get("trailingPE"), 2),
        "fpe": n(f.get("forwardPE"), 2),
        "pb": n(f.get("priceToBook"), 2),
        "roe": n(f.get("returnOnEquity")),
        "roa": n(f.get("returnOnAssets")),
        "pm": n(f.get("profitMargins")),
        "om": n(f.get("operatingMargins")),
        "gm": n(f.get("grossMargins")),
        "revg": n(f.get("revenueGrowth")),
        "earng": n(f.get("earningsGrowth")),
        "de": n(f.get("debtToEquity")),
        "cr": n(f.get("currentRatio"), 2),
        "fcf_cr": n(f.get("freeCashflow")),
        "divy": n(f.get("dividendYield")),
        "payout": n(f.get("payoutRatio")),
        "beta": n(f.get("beta"), 2),
        "target": n(f.get("targetMeanPrice"), 2),
        "n_analysts": f.get("numberOfAnalystOpinions"),
        "rec": f.get("recommendationKey"),
        "sector": (f.get("sector") or "")[:22],
        "industry": (f.get("industry") or "")[:26],
        "insiders": n(f.get("heldPercentInsiders")),
        "insts": n(f.get("heldPercentInstitutions")),
        "summary": (f.get("longBusinessSummary") or "").strip(),
    })

json.dump(rows, open(os.path.join(P, "analysis_rows.json"), "w", encoding="utf-8"), indent=2)

def f(v, pct=False, scale=1.0):
    if v is None:
        return "n/a"
    s = ("%.2f" % (v * 100)) if pct else ("%.2f" % v)
    return s

lines = []
lines.append("# Analysis brief: Indian equity watchlist\n")
lines.append("Budget: **Rs 3,500**. Indian equities trade in whole shares only, no fractional units.")
lines.append("Every price is the last close from Yahoo Finance. Fundamental figures are Yahoo's")
lines.append("own trailing twelve month and reported figures, not adjusted or restated.\n")
lines.append("| ticker | name | group | price | PE | fwd PE | P/B | ROE | profit mgn | op mgn | gross mgn | rev growth | earn growth | D/E | curr ratio | div yield | mcap (cr) | 52w low | 52w high | analyst target |")
lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        r["ticker"], r["name"][:24], r["group"], r["price"], f(r["pe"]), f(r["fpe"]), f(r["pb"]),
        f(r["roe"], True), f(r["pm"], True), f(r["om"], True), f(r["gm"], True),
        f(r["revg"], True), f(r["earng"], True), f(r["de"]), f(r["cr"]), f(r["divy"], True),
        f(r["mcap_cr"], False, 1), r["yr_low"], r["yr_high"], f(r["target"], False, 1)))

lines.append("\n## Full business summaries\n")
for r in rows:
    lines.append("### %s  (%s)" % (r["ticker"], r["name"]))
    lines.append("- sector: %s | industry: %s | group: %s" % (r["sector"], r["industry"], r["group"]))
    lines.append("- insider holding %s | institutional holding %s | analyst consensus %s (%s analysts) | beta %s" % (
        f(r["insiders"], True), f(r["insts"], True), r["rec"], r["n_analysts"], r["beta"]))
    if r["summary"]:
        lines.append("- %s" % r["summary"][:900])
    lines.append("")

open(os.path.join(P, "analysis_brief.md"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote trader/analysis_brief.md (%d unique stocks) and trader/analysis_rows.json" % len(rows))
