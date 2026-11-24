"""Tests for the NSE and BSE (India) support added in this fork.

Everything here runs offline. It checks the ticker rules, the Indian market
clock, the currency rendering and the Indian capital gains rules.
"""

import datetime
import json
import os
import unittest

from _load import ROOT, load

alerts = load("trader-alerts", "alerts")
news = load("trader-news", "news")
risk = load("trader-risk", "check")
budget = load("trader-budget", "size")
tax = load("trader-tax", "lots")
rebalance = load("trader-rebalance", "rebalance")
broker = load("trader-broker", "ticket")


class YahooSymbols(unittest.TestCase):
    """A Yahoo symbol keeps the dot for Indian tickers and loses it for US class shares."""

    def test_indian_tickers_keep_the_dot(self):
        for sym in ("RELIANCE.NS", "TCS.BO", "INFY.NS", "HDFCBANK.NS", "NIFTYBEES.NS"):
            self.assertEqual(alerts.yahoo_symbol(sym), sym.upper())
            self.assertEqual(news.yahoo_symbol(sym), sym.upper())

    def test_us_class_shares_still_become_a_dash(self):
        self.assertEqual(alerts.yahoo_symbol("BRK.B"), "BRK-B")
        self.assertEqual(news.yahoo_symbol("BRK.B"), "BRK-B")

    def test_plain_tickers_are_uppercased(self):
        self.assertEqual(alerts.yahoo_symbol("aapl"), "AAPL")
        self.assertEqual(news.yahoo_symbol("aapl"), "AAPL")

    def test_the_yahoo_url_keeps_the_indian_suffix(self):
        self.assertIn("/chart/RELIANCE.NS?", alerts.yahoo_url("RELIANCE.NS"))
        self.assertIn("/chart/BRK-B?", alerts.yahoo_url("BRK.B"))


class MarketDetection(unittest.TestCase):
    def test_indian_suffixes_select_the_indian_market(self):
        self.assertEqual(alerts.market_of("RELIANCE.NS"), "IN")
        self.assertEqual(alerts.market_of("TCS.BO"), "IN")
        self.assertEqual(alerts.market_of("reliance.ns"), "IN")

    def test_us_tickers_stay_on_the_us_market(self):
        self.assertEqual(alerts.market_of("AAPL"), "US")
        self.assertEqual(alerts.market_of("BRK.B"), "US")


class TickerValidation(unittest.TestCase):
    ACCEPTED = ["AAPL", "BRK.B", "BRK-B", "INFY", "TCS.BO", "RELIANCE.NS", "HDFCBANK.NS",
                "BAJAJ-AUTO.NS", "M&M.NS", "L&T.NS", "TATAMOTORS.BO", "NIFTYBEES.NS",
                "COALINDIA.NS"]

    def test_us_and_indian_tickers_are_accepted(self):
        for t in self.ACCEPTED:
            self.assertTrue(risk.valid_ticker(t), t)

    def test_crypto_options_and_nonsense_are_rejected(self):
        for t in ("BTC/USD", "AAPL 260116C00150000", "aapl", "TOO-LONG-TICKER-NAME-HERE", ""):
            self.assertFalse(risk.valid_ticker(t), t)

    def test_an_indian_ticker_does_not_look_like_an_option(self):
        self.assertIsNone(risk.OCC.match("COALINDIA.NS"))
        self.assertIsNone(risk.OCC.match("RELIANCE.NS"))

    def test_the_us_pattern_still_rejects_indian_tickers(self):
        self.assertIsNone(risk.US_TICKER.match("RELIANCE.NS"))
        self.assertIsNotNone(risk.US_TICKER.match("AAPL"))


class IndianCalendar(unittest.TestCase):
    """The NSE holiday table, checked against the published 2026 list."""

    # Four of the twenty fall on a weekend, so they do not cost a trading day.
    WEEKEND_DATED = {"2026-02-15", "2026-03-21", "2026-08-15", "2026-11-08"}

    def test_the_table_has_twenty_entries(self):
        self.assertEqual(len(alerts.NSE_HOLIDAYS), 20)

    def test_every_date_is_a_real_2026_date(self):
        for d in alerts.NSE_HOLIDAYS:
            day = datetime.date.fromisoformat(d)
            self.assertEqual(day.year, 2026, d)

    def test_the_weekday_closures_are_weekdays(self):
        for d in alerts.NSE_HOLIDAYS:
            day = datetime.date.fromisoformat(d)
            if d in self.WEEKEND_DATED:
                self.assertGreaterEqual(day.weekday(), 5, d)
            else:
                self.assertLess(day.weekday(), 5, d)

    def test_the_known_holidays_are_present(self):
        for d in ("2026-01-26", "2026-08-15", "2026-10-02", "2026-12-25"):
            self.assertIn(d, alerts.NSE_HOLIDAYS)

    def test_a_holiday_is_not_a_trading_day(self):
        day = datetime.date(2026, 1, 26)
        ok, reason = alerts.trading_day(day, "IN")
        self.assertFalse(ok)
        self.assertIn("NSE holiday", reason)

    def test_a_weekend_is_not_a_trading_day(self):
        ok, reason = alerts.trading_day(datetime.date(2026, 11, 21), "IN")
        self.assertFalse(ok)
        self.assertEqual(reason, "weekend")

    def test_a_plain_working_day_is_a_trading_day(self):
        ok, _ = alerts.trading_day(datetime.date(2026, 11, 20), "IN")
        self.assertTrue(ok)

    def test_the_us_calendar_is_untouched(self):
        ok, reason = alerts.trading_day(datetime.date(2026, 1, 1), "US")
        self.assertFalse(ok)
        self.assertIn("NYSE holiday", reason)
        ok, _ = alerts.trading_day(datetime.date(2026, 1, 26), "US")
        self.assertTrue(ok)


class IndianClock(unittest.TestCase):
    def test_the_session_is_0915_to_1530(self):
        s = alerts.session(datetime.date(2026, 11, 20), "IN")
        self.assertEqual(s, (datetime.time(9, 15), datetime.time(15, 30)))

    def test_ist_is_a_fixed_plus_530(self):
        utc = datetime.datetime(2026, 11, 24, 4, 0, 0)
        self.assertEqual(alerts.to_ist(utc), datetime.datetime(2026, 11, 24, 9, 30, 0))

    def test_the_market_is_open_inside_the_indian_session(self):
        # 10:00 IST is 04:30 UTC.
        st = alerts.market_status(datetime.datetime(2026, 11, 20, 4, 30, 0), "IN")
        self.assertTrue(st["open"])
        self.assertEqual(st["opens"], "09:15")
        self.assertEqual(st["closes"], "15:30")

    def test_the_market_is_closed_outside_the_indian_session(self):
        # 20:00 IST is 14:30 UTC.
        st = alerts.market_status(datetime.datetime(2026, 11, 20, 14, 30, 0), "IN")
        self.assertFalse(st["open"])

    def test_the_2027_indian_calendar_is_not_claimed_to_be_known(self):
        st = alerts.market_status(datetime.datetime(2027, 1, 4, 4, 30, 0), "IN")
        self.assertFalse(st["calendar_known"])

    def test_the_us_clock_is_untouched(self):
        st = alerts.market_status(datetime.datetime(2026, 11, 20, 15, 0, 0), "US")
        self.assertEqual(st["opens"], "09:30")
        self.assertEqual(st["closes"], "16:00")
        self.assertIn("now_new_york", st)


class Currency(unittest.TestCase):
    def tearDown(self):
        for mod in (alerts, risk, budget, tax, rebalance, broker):
            if hasattr(mod, "CURRENCY"):
                mod.CURRENCY = "USD"

    def test_dollars_render_the_same_as_before(self):
        self.assertEqual(risk.money(1250), "$1,250")
        self.assertEqual(budget.money(1250), "$1,250")
        self.assertEqual(budget.money(1250.5), "$1,250.50")
        self.assertEqual(tax.money(1250), "$1,250.00")
        self.assertEqual(rebalance.money(1250), "$1,250")
        self.assertEqual(broker._money("1250"), "$1,250")

    def test_rupees_render_with_the_rupee_prefix(self):
        risk.CURRENCY = "INR"
        self.assertEqual(risk.money(1250), "Rs 1,250")
        budget.CURRENCY = "INR"
        self.assertEqual(budget.money(1250), "Rs 1,250")
        tax.CURRENCY = "INR"
        self.assertEqual(tax.money(1250), "Rs 1,250.00")
        rebalance.CURRENCY = "INR"
        self.assertEqual(rebalance.money(1250), "Rs 1,250")
        broker.CURRENCY = "INR"
        self.assertEqual(broker._money("1250"), "Rs 1,250")

    def test_an_unknown_currency_falls_back_to_the_code(self):
        risk.CURRENCY = "ZAR"
        self.assertEqual(risk.money(10), "ZAR 10")

    def test_the_config_example_carries_the_new_keys(self):
        with open(os.path.join(ROOT, "trader-budget", "config.example.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertEqual(cfg["currency"], "USD")
        self.assertEqual(cfg["market"], "US")


class OrderSizeAliases(unittest.TestCase):
    def test_the_neutral_alias_wins_over_the_usd_key(self):
        cfg = {"budget": 5000, "max_order_usd": 2000, "max_order": 500, "min_order_usd": 5,
               "min_order": 50}
        result = risk.check([{"symbol": "RELIANCE.NS", "side": "buy", "notional": "1000",
                              "type": "market", "time_in_force": "day"}], cfg)
        self.assertEqual(result["pass"], 0)
        self.assertEqual(result["block"], 1)
        self.assertIn("max order", result["results"][0]["reasons"][0])

    def test_the_usd_key_still_works(self):
        cfg = {"budget": 5000, "max_order_usd": 2000, "min_order_usd": 5}
        result = risk.check([{"symbol": "AAPL", "side": "buy", "notional": "1000",
                              "type": "market", "time_in_force": "day"}], cfg)
        self.assertEqual(result["pass"], 1)
        self.assertEqual(result["block"], 0)


class NewsMentions(unittest.TestCase):
    def test_indian_exchange_prefixes_are_matched(self):
        pats = news.mention_patterns({"RELIANCE.NS": "Reliance Industries"})
        self.assertTrue(pats["RELIANCE.NS"].search("NSE: RELIANCE jumps 4 percent"))
        self.assertTrue(pats["RELIANCE.NS"].search("BSE: RELIANCE jumps 4 percent"))

    def test_us_exchange_prefixes_still_match(self):
        pats = news.mention_patterns({"AAPL": "Apple Inc"})
        self.assertTrue(pats["AAPL"].search("NASDAQ: AAPL rises"))

    def test_an_unrelated_headline_does_not_match(self):
        pats = news.mention_patterns({"RELIANCE.NS": "Reliance Industries"})
        self.assertIsNone(pats["RELIANCE.NS"].search("Sensex closed higher on Friday"))


class IndianTaxRules(unittest.TestCase):
    def setUp(self):
        self.market = tax.MARKET
        self.currency = tax.CURRENCY

    def tearDown(self):
        tax.MARKET = self.market
        tax.CURRENCY = self.currency

    def test_the_us_rules_are_unchanged(self):
        rules = tax.TAX_RULES["US"]
        self.assertTrue(rules["wash_sale"])
        self.assertEqual(rules["stcg_rate"], 0.0)
        self.assertEqual(rules["ltcg_rate"], 0.0)
        self.assertEqual(rules["cess_rate"], 0.0)
        self.assertEqual(rules["stt_sell_rate"], 0.0)

    def test_the_indian_rules(self):
        rules = tax.TAX_RULES["IN"]
        self.assertFalse(rules["wash_sale"])
        self.assertEqual(rules["stcg_rate"], 0.20)
        self.assertEqual(rules["ltcg_rate"], 0.125)
        self.assertEqual(rules["cess_rate"], 0.04)
        self.assertEqual(rules["stt_sell_rate"], 0.001)

    def test_the_effective_indian_rates(self):
        rules = tax.TAX_RULES["IN"]
        self.assertAlmostEqual(rules["stcg_rate"] * (1 + rules["cess_rate"]), 0.208)
        self.assertAlmostEqual(rules["ltcg_rate"] * (1 + rules["cess_rate"]), 0.13)

    def test_the_long_term_threshold_is_twelve_months(self):
        tax.MARKET = "IN"
        bought = datetime.date(2024, 1, 1)
        self.assertEqual(tax.term(bought, datetime.date(2024, 12, 31)), "short")
        self.assertEqual(tax.term(bought, datetime.date(2025, 1, 2)), "long")

    def test_the_us_long_term_rule_is_unchanged(self):
        tax.MARKET = "US"
        bought = datetime.date(2024, 1, 1)
        self.assertEqual(tax.term(bought, datetime.date(2024, 12, 31)), "short")
        self.assertEqual(tax.term(bought, datetime.date(2025, 1, 2)), "long")

    def test_the_estimated_tax_uses_the_rate_with_cess(self):
        tax.MARKET = "IN"
        amount, rate = tax.tax_for(100000, 100000, "short")
        self.assertAlmostEqual(rate, 0.208)
        # 100000 of gain at 20.8 percent, plus 0.1 percent STT on the sale.
        self.assertAlmostEqual(amount, 100000 * 0.208 + 100000 * 0.001, places=2)

    def test_the_estimated_long_term_tax(self):
        tax.MARKET = "IN"
        amount, rate = tax.tax_for(100000, 100000, "long")
        self.assertAlmostEqual(rate, 0.13)
        self.assertAlmostEqual(amount, 100000 * 0.13 + 100000 * 0.001, places=2)

    def test_no_tax_is_estimated_for_the_us_market(self):
        tax.MARKET = "US"
        amount, rate = tax.tax_for(100000, 100000, "long")
        self.assertEqual(amount, 0.0)
        self.assertEqual(rate, 0.0)

    def test_a_loss_is_not_taxed(self):
        tax.MARKET = "IN"
        amount, rate = tax.tax_for(-5000, 100000, "short")
        self.assertEqual(amount, 100000 * 0.001)

    def test_india_has_no_wash_sale(self):
        tax.MARKET = "IN"
        hits = tax.wash_check("AAPL", datetime.date(2026, 3, 1), [], {"positions": []}, [], {})
        self.assertEqual(hits, [])

    def test_the_us_wash_sale_still_fires(self):
        tax.MARKET = "US"
        # The sold lot is AAPL-1. AAPL-2 was bought inside the 30 day window and
        # is still held, so it is a replacement purchase.
        portfolio = {"positions": [{"ticker": "AAPL", "shares": 15,
                                    "lots": [{"id": "AAPL-1", "date": "2026-02-25",
                                              "shares": 10, "cost": 1000},
                                             {"id": "AAPL-2", "date": "2026-02-28",
                                              "shares": 5, "cost": 500}]}]}
        used = [{"id": "AAPL-1", "acquired": "2026-02-25", "shares": 10, "basis": 1000.0,
                 "proceeds": 900.0, "gain": -100.0, "term": "short"}]
        hits = tax.wash_check("AAPL", datetime.date(2026, 3, 1), used, portfolio, [], {})
        self.assertTrue(hits)
        self.assertEqual(hits[0]["ticker"], "AAPL")


class NoEmDashes(unittest.TestCase):
    def test_no_em_dash_anywhere_in_the_sources(self):
        for folder in ("trader-alerts", "trader-news", "trader-budget", "trader-risk",
                       "trader-tax", "trader-broker", "trader-rebalance"):
            for name in os.listdir(os.path.join(ROOT, folder)):
                if name.endswith((".py", ".md", ".json")):
                    path = os.path.join(ROOT, folder, name)
                    with open(path, encoding="utf-8") as fh:
                        self.assertNotIn("\u2014", fh.read(), path)


if __name__ == "__main__":
    unittest.main()
