"""Fetch Yahoo fundamentals for the whole Nifty 500, in parallel.

Each worker thread keeps its own cookie jar and crumb so nothing is shared
across threads. Output:
  trader/nifty500_metrics.csv   flat metrics in the shape trader-screener reads
  trader/nifty500.json          everything, for the analysis agents
"""

import csv, json, os, ssl, sys, threading, time, urllib.request, urllib.parse, http.cookiejar

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "trader")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
WORKERS = 8

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), urllib.request.HTTPSHandler(context=ctx))
        self.opener.addheaders = [("User-Agent", UA), ("Accept", "application/json,text/plain,*/*")]
        self.crumb = None

    def get(self, url, tries=3):
        for i in range(tries):
            try:
                with self.opener.open(url, timeout=30) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(2.5 * (i + 1))
                    continue
                return None
            except Exception:
                if i == tries - 1:
                    return None
                time.sleep(1.0 * (i + 1))
        return None

    def boot(self):
        self.get("https://fc.yahoo.com")
        self.get("https://finance.yahoo.com/quote/RELIANCE.NS")
        c = self.get("https://query1.finance.yahoo.com/v1/test/getcrumb")
        if c and len(c) < 40 and "\n" not in c:
            self.crumb = c.strip()


def search_symbol(client, query):
    txt = client.get("https://query1.finance.yahoo.com/v1/finance/search?q=%s&quotesCount=10&newsCount=0"
                     % urllib.parse.quote(query))
    if not txt:
        return None
    try:
        data = json.loads(txt)
    except Exception:
        return None
    for q in data.get("quotes", []):
        s = q.get("symbol") or ""
        if q.get("quoteType") == "EQUITY" and (s.endswith(".NS") or s.endswith(".BO")):
            return s
    return None


def chart_meta(client, symbol):
    txt = client.get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1y&interval=1d"
                     % urllib.parse.quote(symbol, safe=""))
    if not txt:
        return None
    try:
        r = json.loads(txt)["chart"]["result"][0]
    except Exception:
        return None
    m = r["meta"]
    closes = [c for c in (r["indicators"]["quote"][0].get("close") or []) if c is not None]
    return {"price": m.get("regularMarketPrice"), "currency": m.get("currency"),
            "exchange": m.get("fullExchangeName"), "name": m.get("longName") or m.get("shortName"),
            "yr_low": min(closes) if closes else None, "yr_high": max(closes) if closes else None}


def quote_summary(client, symbol):
    if not client.crumb:
        return {}
    mods = "summaryDetail,financialData,defaultKeyStatistics,price,assetProfile"
    txt = client.get("https://query2.finance.yahoo.com/v10/finance/quoteSummary/%s?modules=%s&crumb=%s"
                     % (urllib.parse.quote(symbol), mods, urllib.parse.quote(client.crumb)))
    if not txt:
        return {}
    try:
        res = json.loads(txt)["quoteSummary"]["result"][0]
    except Exception:
        return {}

    def g(mod, key):
        try:
            v = res.get(mod, {}).get(key)
            if isinstance(v, dict):
                v = v.get("raw", v.get("fmt"))
            return v
        except Exception:
            return None

    return {
        "sector": g("assetProfile", "sector"), "industry": g("assetProfile", "industry"),
        "longBusinessSummary": g("assetProfile", "longBusinessSummary"),
        "marketCap": g("price", "marketCap"),
        "trailingPE": g("summaryDetail", "trailingPE"), "forwardPE": g("summaryDetail", "forwardPE"),
        "priceToBook": g("defaultKeyStatistics", "priceToBook"),
        "returnOnEquity": g("financialData", "returnOnEquity"),
        "returnOnAssets": g("financialData", "returnOnAssets"),
        "profitMargins": g("financialData", "profitMargins"),
        "operatingMargins": g("financialData", "operatingMargins"),
        "grossMargins": g("financialData", "grossMargins"),
        "revenueGrowth": g("financialData", "revenueGrowth"),
        "earningsGrowth": g("financialData", "earningsGrowth"),
        "debtToEquity": g("financialData", "debtToEquity"),
        "currentRatio": g("financialData", "currentRatio"),
        "freeCashflow": g("financialData", "freeCashflow"),
        "targetMeanPrice": g("financialData", "targetMeanPrice"),
        "recommendationKey": g("financialData", "recommendationKey"),
        "numberOfAnalystOpinions": g("financialData", "numberOfAnalystOpinions"),
        "dividendYield": g("summaryDetail", "dividendYield"),
        "payoutRatio": g("summaryDetail", "payoutRatio"),
        "beta": g("summaryDetail", "beta"),
        "sharesOutstanding": g("defaultKeyStatistics", "sharesOutstanding"),
        "heldPercentInsiders": g("defaultKeyStatistics", "heldPercentInsiders"),
        "heldPercentInstitutions": g("defaultKeyStatistics", "heldPercentInstitutions"),
        "totalRevenue": g("financialData", "totalRevenue"),
        "netIncomeToCommon": g("financialData", "netIncomeToCommon"),
    }


NAMES = {}
with open(os.path.join(OUT, "nifty500.csv"), encoding="utf-8", errors="replace") as fh:
    for row in csv.DictReader(fh):
        sym = (row.get("Symbol") or "").strip()
        if sym:
            NAMES[sym] = {"name": (row.get("Company Name") or "").strip(),
                          "industry": (row.get("Industry") or "").strip()}

print("constituents: %d" % len(NAMES))
results = {}
lock = threading.Lock()
done = [0]


def work(item):
    sym, meta = item
    c = Client()
    c.boot()
    ysym = sym + ".NS"
    cm = chart_meta(c, ysym)
    if not cm:
        alt = search_symbol(c, sym)
        if alt and alt != ysym:
            ysym = alt
            cm = chart_meta(c, ysym)
    if not cm:
        with lock:
            results[sym] = {"symbol": None, "resolved": False}
            done[0] += 1
        return
    time.sleep(0.2)
    fs = quote_summary(c, ysym)
    rec = {"symbol": ysym, "resolved": True, "nse_name": meta["name"], "industry": meta["industry"],
           "chart": cm, "fundamentals": fs}
    with lock:
        results[sym] = rec
        done[0] += 1
        if done[0] % 50 == 0:
            print("  %d/%d" % (done[0], len(NAMES)), flush=True)


items = list(NAMES.items())
q = list(items)
threads = []
for i in range(WORKERS):
    def run():
        while True:
            try:
                item = q.pop(0)
            except IndexError:
                return
            work(item)
    t = threading.Thread(target=run)
    threads.append(t)
    t.start()
for t in threads:
    t.join()

print("resolved %d of %d" % (sum(1 for v in results.values() if v.get("resolved")), len(NAMES)))
with open(os.path.join(OUT, "nifty500.json"), "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=2, ensure_ascii=False)

COLS = [
    ("ticker", lambda r, f, c, n: r["symbol"]),
    ("name", lambda r, f, c, n: (n.get("name") or "")[:36]),
    ("industry", lambda r, f, c, n: (n.get("industry") or "")[:26]),
    ("price", lambda r, f, c, n: c.get("price")),
    ("market_cap", lambda r, f, c, n: f.get("marketCap")),
    ("pe", lambda r, f, c, n: f.get("trailingPE")),
    ("forward_pe", lambda r, f, c, n: f.get("forwardPE")),
    ("price_to_book", lambda r, f, c, n: f.get("priceToBook")),
    ("roe", lambda r, f, c, n: f.get("returnOnEquity")),
    ("profit_margin", lambda r, f, c, n: f.get("profitMargins")),
    ("operating_margin", lambda r, f, c, n: f.get("operatingMargins")),
    ("revenue_growth", lambda r, f, c, n: f.get("revenueGrowth")),
    ("earnings_growth", lambda r, f, c, n: f.get("earningsGrowth")),
    ("debt_equity", lambda r, f, c, n: f.get("debtToEquity")),
    ("dividend_yield", lambda r, f, c, n: f.get("dividendYield")),
    ("yr_low", lambda r, f, c, n: c.get("yr_low")),
    ("yr_high", lambda r, f, c, n: c.get("yr_high")),
    ("analyst_target", lambda r, f, c, n: f.get("targetMeanPrice")),
    ("analyst_count", lambda r, f, c, n: f.get("numberOfAnalystOpinions")),
    ("insiders", lambda r, f, c, n: f.get("heldPercentInsiders")),
]

path = os.path.join(OUT, "nifty500_metrics.csv")
with open(path, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow([c for c, _ in COLS])
    for sym, r in sorted(results.items()):
        if not r.get("resolved"):
            continue
        f = r.get("fundamentals") or {}
        c = r.get("chart") or {}
        n = NAMES.get(sym, {})
        row = []
        for _, fn in COLS:
            v = fn(r, f, c, n)
            if isinstance(v, float):
                v = round(v, 6)
            row.append("" if v is None else v)
        w.writerow(row)
print("wrote trader/nifty500_metrics.csv")
