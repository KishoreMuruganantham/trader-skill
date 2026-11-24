"""Exact Indian delivery-trade cost model for 2026, and a portfolio constructor.

Equity delivery on Zerodha style brokers:
  brokerage        0 on delivery
  stamp duty       0.015 percent, buy side only
  STT              0.1 percent, sell side only
  NSE txn charges  0.00297 percent, both sides
  SEBI             10 per crore = 0.0001 percent, both sides
  GST              18 percent on (exchange charges + SEBI)
  DP charges       15.34 per scrip, sell side only
"""

import csv, json, os, sys

BUDGET = 3500.0
BUY_TXN = 0.0000297 + 0.000001        # exchange + SEBI
SELL_TXN = 0.0000297 + 0.000001
STAMP = 0.00015
STT_SELL = 0.001
GST = 0.18
DP_PER_SCRIP = 15.34


def buy_cost(turnover):
    return turnover * (STAMP + BUY_TXN * (1 + GST))


def sell_cost(turnover, scrips):
    return (turnover * (STT_SELL + SELL_TXN * (1 + GST))) + DP_PER_SCRIP * scrips


def round_trip(turnover, scrips):
    return buy_cost(turnover) + sell_cost(turnover, scrips)


def load_prices(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("price"):
                out[r["ticker"]] = float(r["price"])
    return out


def evaluate(holdings, prices, budget=BUDGET):
    """holdings: {ticker: shares}. Returns a dict with the arithmetic."""
    rows = []
    invested = 0.0
    for t, qty in holdings.items():
        p = prices.get(t)
        if p is None:
            continue
        amt = p * qty
        invested += amt
        rows.append({"ticker": t, "qty": qty, "price": p, "amount": amt})
    rows.sort(key=lambda r: -r["amount"])
    scrips = len(rows)
    buy = buy_cost(invested)
    sell = sell_cost(invested, scrips)
    cash = budget - invested
    return {
        "holdings": rows,
        "invested": round(invested, 2),
        "cash_left": round(cash, 2),
        "scrips": scrips,
        "buy_cost": round(buy, 2),
        "sell_cost": round(sell, 2),
        "total_cost": round(buy + sell, 2),
        "cost_pct": round((buy + sell) / budget * 100, 2),
        "weights": {r["ticker"]: round(r["amount"] / invested * 100, 1) for r in rows},
        "fits": invested <= budget,
        "worst_weight": max((r["amount"] / invested * 100 for r in rows), default=0),
    }


def show(name, holdings, prices):
    res = evaluate(holdings, prices)
    print("\n%s" % name)
    print("-" * len(name))
    for r in res["holdings"]:
        print("  %-16s %4d x Rs %9.2f = Rs %9.2f   %5.1f%%" % (
            r["ticker"], r["qty"], r["price"], r["amount"], res["weights"][r["ticker"]]))
    print("  %-16s %38s = Rs %9.2f" % ("invested", "", res["invested"]))
    print("  %-16s %38s = Rs %9.2f" % ("cash left", "", res["cash_left"]))
    print("  %-16s %38s = Rs %9.2f" % ("buy charges", "", res["buy_cost"]))
    print("  %-16s %38s = Rs %9.2f  (%d scrip x Rs %.2f)" % (
        "sell charges", "", res["sell_cost"], res["scrips"], DP_PER_SCRIP))
    print("  %-16s %38s = Rs %9.2f   (%.2f%% of the Rs %.0f budget)" % (
        "total charges", "", res["total_cost"], res["cost_pct"], BUDGET))
    if res["worst_weight"] > 40:
        print("  WARNING: the largest position is %.1f%% of the invested amount" % res["worst_weight"])
    return res


if __name__ == "__main__":
    P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trader")
    prices = load_prices(os.path.join(P, "metrics.csv"))

    print("Cost of the DP charge alone, by number of scrips:")
    for n in (1, 2, 3, 4, 5, 6):
        c = round_trip(3000, n)
        print("  %d scrip(s): Rs %6.2f round trip = %.2f%% of Rs 3,500" % (n, c, c / BUDGET * 100))

    print("\nThe same Rs 3,000 of turnover costs very differently by scrip count:")
    for n in (1, 3, 5):
        c = round_trip(3000, n)
        print("  %d scrip(s): Rs %6.2f  (%.2f%% of capital)" % (n, c, c / 3000 * 100))
