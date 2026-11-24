# India research kit: 35-stock watchlist, 24 November 2026

This folder is the working paper behind an India-market review of a 35-stock
watchlist, run with a Rs 3,500 budget. It is a research artefact, not part of
the skill pack. The skills themselves are unchanged.

## What is here

| file | what it is |
|---|---|
| `fetch_fundamentals.py` | Pulls price and trailing fundamentals for every ticker from Yahoo Finance, resolves the symbol by search, and writes `output/metrics.csv` and `output/fundamentals.json`. |
| `build_brief.py` | Turns `fundamentals.json` into `output/analysis_brief.md`, the table the analysis agents read. |
| `costs.py` | Exact Indian equity delivery cost model and a portfolio constructor. This is the part that matters most at a small budget. |
| `output/analysis_brief.md` | All 35 stocks: price, PE, forward PE, P/B, ROE, margins, growth, leverage, 52 week range, analyst target, plus a business summary for each. |
| `output/quality_scores.md` | A Buffett quality screen, five axes scored out of 5 each, with researched red flags. |
| `output/valuation.md` | Price against each stock's own five year history, value traps, stretched names. |
| `output/sector_memo.md` | Macro backdrop and sector ranking, with every macro fact dated and sourced. |
| `output/final_portfolio.md` | The three candidate portfolios and the reasoning. |
| `output/metrics.csv` | Flat metrics file in the shape `trader-screener` reads. |
| `output/rules.json`, `output/rules_quality_only.json` | Two screener rule sets used in the review. |

## Reproducing it

```bash
python fetch_fundamentals.py      # writes output/metrics.csv and output/fundamentals.json
python build_brief.py             # writes output/analysis_brief.md
python costs.py                   # prints the DP charge effect by scrip count
```

The fetch script needs no API key. It identifies itself to Yahoo with a browser
user agent and requests a crumb, and it pauses between requests.

## Two things worth keeping

**Ticker corrections.** Yahoo's search ranks the wrong company first for several
names, so the fetch script carries an explicit override table with a note on
each. Four corrections that matter:

- `TATAMOTORS.NS` no longer exists. After the 2025 demerger, `TMPV.NS` is Tata
  Motors Passenger Vehicles and `TMCV.NS` is the commercial vehicle business.
- Hexaware Technologies trades as `HEXT.NS`, not `HEXAWARE`.
- Amara Raja Energy and Mobility trades as `ARE&M.NS`, with an ampersand in the
  symbol that has to be URL encoded.
- Tata Sons, which would be the Tata group holding company, is unlisted. There
  is no ticker for it and there never will be.

**Cost of a small portfolio.** Equity delivery brokerage is Rs 0, so the cost
that decides whether a Rs 3,500 portfolio is worth splitting is the DP charge of
Rs 15.34 per scrip on the sell side. One scrip costs about 0.63 percent of
capital round trip, five scrips cost about 2.68 percent. Splitting a small
sum across more names is expensive, and that changes the answer.

## The scripts behind the skills

The screener rule sets above were run through the `trader-screener` skill, and
the resulting portfolio through `trader-budget` and `trader-risk`. The Indian
support those skills need, including the Yahoo symbol fix, the ticker regex,
the rupee formatting and the Indian capital gains rules, is in this fork.

Not financial advice. Arithmetic on public data, and a point of view.
