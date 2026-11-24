"""Fetch Indian equity fundamentals from Yahoo Finance for the watchlist.

Uses the public chart/search endpoints plus a cookie + crumb pair for the
fundamentals endpoints. Writes two artefacts:
  trader/metrics.csv   the shape trader-screener reads (ticker plus metrics)
  trader/fundamentals.json  everything, for the analysis agents
"""

import json, os, ssl, sys, time, urllib.request, urllib.parse, http.cookiejar, csv, re

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trader")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPSHandler(context=ctx))
opener.addheaders = [("User-Agent", UA), ("Accept", "application/json,text/plain,*/*"),
                     ("Accept-Language", "en-US,en;q=0.9")]


def get(url, tries=3):
    for i in range(tries):
        try:
            with opener.open(url, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if i == tries - 1:
                return None
            time.sleep(1.5 * (i + 1))
    return None


def boot():
    get("https://fc.yahoo.com")
    get("https://finance.yahoo.com/quote/TCS.NS")
    crumb = get("https://query1.finance.yahoo.com/v1/test/getcrumb")
    if crumb and len(crumb) < 40 and "\n" not in crumb:
        return crumb.strip()
    return None


CRUMB = boot()
print("crumb:", (CRUMB[:6] + "...") if CRUMB else "NONE (fundamentals endpoints will fail)")


def search_symbol(query):
    url = "https://query1.finance.yahoo.com/v1/finance/search?q=%s&quotesCount=10&newsCount=0" % urllib.parse.quote(query)
    txt = get(url)
    if not txt:
        return None
    try:
        data = json.loads(txt)
    except Exception:
        return None
    for q in data.get("quotes", []):
        if q.get("quoteType") == "EQUITY" and q.get("symbol") and \
                (q.get("symbol").endswith(".NS") or q.get("symbol").endswith(".BO")):
            return {"symbol": q["symbol"], "name": q.get("shortname") or q.get("longname") or "",
                    "exchange": q.get("fullExchangeName") or q.get("exchDisp") or ""}
    return None


def chart_meta(symbol):
    txt = get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1y&interval=1d"
              % urllib.parse.quote(symbol, safe=""))
    if not txt:
        return None
    try:
        r = json.loads(txt)["chart"]["result"][0]
    except Exception:
        return None
    m = r["meta"]
    closes = [c for c in (r["indicators"]["quote"][0].get("close") or []) if c is not None]
    yr = {"last": closes[-1] if closes else None,
          "yr_low": min(closes) if closes else None,
          "yr_high": max(closes) if closes else None}
    return {"price": m.get("regularMarketPrice"), "currency": m.get("currency"),
            "exchange": m.get("fullExchangeName"), "name": m.get("longName") or m.get("shortName"),
            **yr}


def quote_summary(symbol):
    if not CRUMB:
        return {}
    mods = "summaryDetail,financialData,defaultKeyStatistics,price,assetProfile,summaryProfile"
    url = ("https://query2.finance.yahoo.com/v10/finance/quoteSummary/%s?modules=%s&crumb=%s"
           % (urllib.parse.quote(symbol), mods, urllib.parse.quote(CRUMB)))
    txt = get(url)
    if not txt:
        return {}
    try:
        res = json.loads(txt)["quoteSummary"]["result"][0]
    except Exception:
        return {}

    def g(mod, key, default=None):
        try:
            v = res.get(mod, {}).get(key)
            if isinstance(v, dict):
                v = v.get("raw", v.get("fmt"))
            return default if v is None else v
        except Exception:
            return default

    out = {
        "sector": g("assetProfile", "sector"),
        "industry": g("assetProfile", "industry"),
        "longBusinessSummary": g("assetProfile", "longBusinessSummary"),
        "marketCap": g("price", "marketCap"),
        "trailingPE": g("summaryDetail", "trailingPE"),
        "forwardPE": g("summaryDetail", "forwardPE"),
        "priceToBook": g("defaultKeyStatistics", "priceToBook"),
        "bookValue": g("defaultKeyStatistics", "bookValue"),
        "returnOnEquity": g("financialData", "returnOnEquity"),
        "returnOnAssets": g("financialData", "returnOnAssets"),
        "profitMargins": g("financialData", "profitMargins"),
        "operatingMargins": g("financialData", "operatingMargins"),
        "grossMargins": g("financialData", "grossMargins"),
        "ebitdaMargins": g("financialData", "ebitdaMargins"),
        "revenueGrowth": g("financialData", "revenueGrowth"),
        "earningsGrowth": g("financialData", "earningsGrowth"),
        "earningsQuarterlyGrowth": g("financialData", "earningsQuarterlyGrowth"),
        "debtToEquity": g("financialData", "debtToEquity"),
        "currentRatio": g("financialData", "currentRatio"),
        "quickRatio": g("financialData", "quickRatio"),
        "totalCash": g("financialData", "totalCash"),
        "totalDebt": g("financialData", "totalDebt"),
        "freeCashflow": g("financialData", "freeCashflow"),
        "operatingCashflow": g("financialData", "operatingCashflow"),
        "targetMeanPrice": g("financialData", "targetMeanPrice"),
        "recommendationKey": g("financialData", "recommendationKey"),
        "numberOfAnalystOpinions": g("financialData", "numberOfAnalystOpinions"),
        "dividendYield": g("summaryDetail", "dividendYield"),
        "payoutRatio": g("summaryDetail", "payoutRatio"),
        "beta": g("summaryDetail", "beta"),
        "fiftyTwoWeekHigh": g("summaryDetail", "fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": g("summaryDetail", "fiftyTwoWeekLow"),
        "52WeekChange": g("summaryDetail", "52WeekChange"),
        "earningsTimestamp": g("earningsTimestamp", "earningsTimestampStartDate"),
        "dividendDate": g("summaryDetail", "dividendDate"),
        "sharesOutstanding": g("defaultKeyStatistics", "sharesOutstanding"),
        "floatShares": g("defaultKeyStatistics", "floatShares"),
        "heldPercentInstitutions": g("defaultKeyStatistics", "heldPercentInstitutions"),
        "heldPercentInsiders": g("defaultKeyStatistics", "heldPercentInsiders"),
        "lastDividendValue": g("summaryDetail", "lastDividendValue"),
        "lastSplitFactor": g("summaryDetail", "lastSplitFactor"),
        "enterpriseValue": g("defaultKeyStatistics", "enterpriseValue"),
        "pegRatio": g("defaultKeyStatistics", "pegRatio"),
        "enterpriseToRevenue": g("defaultKeyStatistics", "enterpriseToRevenue"),
        "enterpriseToEbitda": g("defaultKeyStatistics", "enterpriseToEbitda"),
        "revenue": g("financialData", "totalRevenue"),
        "ebitda": g("financialData", "ebitda"),
        "netIncomeToCommon": g("financialData", "netIncomeToCommon"),
        "grossProfit": g("financialData", "grossProfit"),
        "operatingIncome": g("financialData", "operatingIncome"),
    }
    return out


WATCHLIST = json.load(open(os.path.join(OUT_DIR, "watchlist.json"), encoding="utf-8"))

# Names where the Yahoo search ranks the wrong company first, or where the
# listing was renamed. Each entry records why.
OVERRIDES = {
    "Tata motors": ("TMPV.NS", "Tata Motors Passenger Vehicles, the listed Tata Motors after the 2025 demerger"),
    "Tata motors (dup)": ("TMPV.NS", "same as Tata motors"),
    "Indian Hotels": ("INDHOTEL.NS", "search for the full name returned nothing"),
    "Zydus": ("ZYDUSLIFE.NS", "Zydus Life Sciences, the main listed Zydus entity"),
    "Thangamayil Finance": ("THANGAMAYL.NS", "Thangamayil Jewellery, which absorbed Thangamayil Finance"),
    "Amara Raja Energy": ("ARE&M.NS", "renamed Amara Raja Energy and Mobility, ticker contains an ampersand"),
}

results = {}
for group, names in WATCHLIST.items():
    print("\n== %s ==" % group)
    for label, query in names:
        note = ""
        sym = None
        for key in (label, query):
            if key in OVERRIDES:
                sym, note = OVERRIDES[key]
                break
        if not sym:
            if "." in query and query.isupper():
                sym = query
        if not sym:
            hit = search_symbol(query)
            sym = hit["symbol"] if hit else None
        if not sym:
            print("  %-28s UNRESOLVED" % label)
            results[label] = {"group": group, "label": label, "query": query, "resolved": None}
            time.sleep(0.4)
            continue
        meta = chart_meta(sym)
        time.sleep(0.35)
        summary = quote_summary(sym)
        time.sleep(0.55)
        rec = {"group": group, "label": label, "query": query, "symbol": sym,
               "resolved": True, "note": note, "chart": meta, "fundamentals": summary}
        results[label] = rec
        price = (meta or {}).get("price")
        pe = summary.get("trailingPE")
        roe = summary.get("returnOnEquity")
        print("  %-28s -> %-16s Rs %-10s PE %-8s ROE %-8s %s" % (
            label, sym, round(price, 2) if price else "?", round(pe, 1) if pe else "?",
            round(roe * 100, 1) if roe else "?", (meta or {}).get("name", "")[:28]))

os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "fundamentals.json"), "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=2, ensure_ascii=False)
print("\nwrote trader/fundamentals.json with %d entries" % len(results))

# The screener reads a flat CSV. One row per resolved stock.
def num(v):
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    return ""


COLS = [
    ("ticker", lambda r, f, c: r["symbol"]),
    ("name", lambda r, f, c: (c.get("name") or r["label"])[:34]),
    ("sector", lambda r, f, c: (f.get("sector") or "")[:24]),
    ("price", lambda r, f, c: num(c.get("price"))),
    ("market_cap", lambda r, f, c: num(f.get("marketCap"))),
    ("pe", lambda r, f, c: num(f.get("trailingPE"))),
    ("forward_pe", lambda r, f, c: num(f.get("forwardPE"))),
    ("price_to_book", lambda r, f, c: num(f.get("priceToBook"))),
    ("roe", lambda r, f, c: num(f.get("returnOnEquity"))),
    ("roa", lambda r, f, c: num(f.get("returnOnAssets"))),
    ("profit_margin", lambda r, f, c: num(f.get("profitMargins"))),
    ("operating_margin", lambda r, f, c: num(f.get("operatingMargins"))),
    ("revenue_growth", lambda r, f, c: num(f.get("revenueGrowth"))),
    ("earnings_growth", lambda r, f, c: num(f.get("earningsGrowth"))),
    ("debt_equity", lambda r, f, c: num(f.get("debtToEquity"))),
    ("current_ratio", lambda r, f, c: num(f.get("currentRatio"))),
    ("free_cashflow", lambda r, f, c: num(f.get("freeCashflow"))),
    ("dividend_yield", lambda r, f, c: num(f.get("dividendYield"))),
    ("payout_ratio", lambda r, f, c: num(f.get("payoutRatio"))),
    ("beta", lambda r, f, c: num(f.get("beta"))),
    ("yr_low", lambda r, f, c: num(c.get("yr_low"))),
    ("yr_high", lambda r, f, c: num(c.get("yr_high"))),
    ("analyst_target", lambda r, f, c: num(f.get("targetMeanPrice"))),
    ("analyst_count", lambda r, f, c: num(f.get("numberOfAnalystOpinions"))),
    ("recommendation", lambda r, f, c: (f.get("recommendationKey") or "")[:12]),
]

path = os.path.join(OUT_DIR, "metrics.csv")
with open(path, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow([c for c, _ in COLS])
    for label, r in results.items():
        if not r.get("resolved"):
            continue
        f = r.get("fundamentals") or {}
        c = r.get("chart") or {}
        w.writerow([fn(r, f, c) for _, fn in COLS])
print("wrote trader/metrics.csv for trader-screener")

