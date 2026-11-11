import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { analyse, rate, rateOn, rmTotalFromQuote, suggestFlip } from "../fees.js";

const close = (actual, expected, digits = 2) =>
  assert.equal(Number(actual.toFixed(digits)), Number(expected.toFixed(digits)));

describe("buying foreign currency", () => {
  test("bank quote above the real rate", () => {
    // Real RM 4.0560/USD, bank RM 4.1500/USD, buying USD 1,000
    const rmTotal = rmTotalFromQuote({ direction: "buy", foreignAmount: 1000, quotedDisplay: 4.15 });
    const r = analyse({ direction: "buy", foreignAmount: 1000, rmTotal, mid: 4.056 });
    assert.ok(r.ok);
    close(r.fair, 4056);
    close(r.actual, 4150);
    close(r.cost, 94);
    close(r.markupPct, 2.32);
    assert.equal(r.rating.label, "Typical");
  });

  test("fixed fee is added to the cost", () => {
    const rmTotal = rmTotalFromQuote({ direction: "buy", foreignAmount: 1000, quotedDisplay: 4.056, fee: 10 });
    const r = analyse({ direction: "buy", foreignAmount: 1000, rmTotal, mid: 4.056 });
    close(r.cost, 10);
    close(r.effectiveRate, 4.066, 3);
  });

  test("JPY is quoted per 100 units", () => {
    // Real RM 2.5644 per 100 JPY, quote RM 2.70 per 100 JPY, buying 100,000 JPY
    const rmTotal = rmTotalFromQuote({
      direction: "buy",
      foreignAmount: 100000,
      quotedDisplay: 2.7,
      unit: 100,
    });
    close(rmTotal, 2700);
    const r = analyse({ direction: "buy", foreignAmount: 100000, rmTotal, mid: 0.025644 });
    close(r.cost, 135.6);
    close(r.markupPct, 5.29);
    assert.equal(r.rating.label, "Expensive");
  });
});

describe("selling foreign currency", () => {
  test("changer pays less than the real rate", () => {
    const rmTotal = rmTotalFromQuote({ direction: "sell", foreignAmount: 3000, quotedDisplay: 3.1 });
    const r = analyse({ direction: "sell", foreignAmount: 3000, rmTotal, mid: 3.15 });
    close(r.actual, 9300);
    close(r.cost, 150);
    close(r.markupPct, 1.59);
    assert.equal(r.rating.label, "Typical");
  });

  test("fixed fee reduces what you receive", () => {
    const rmTotal = rmTotalFromQuote({ direction: "sell", foreignAmount: 1000, quotedDisplay: 3.15, fee: 15 });
    close(rmTotal, 3135);
  });

  test("fee larger than the amount is an error", () => {
    const rmTotal = rmTotalFromQuote({ direction: "sell", foreignAmount: 1, quotedDisplay: 3.15, fee: 20 });
    const r = analyse({ direction: "sell", foreignAmount: 1, rmTotal, mid: 3.15 });
    assert.equal(r.ok, false);
    assert.match(r.errors[0], /fee bigger than the amount/);
  });
});

describe("'I paid X, got Y' mode", () => {
  test("card statement: RM 2,103.40 charged for USD 500", () => {
    const r = analyse({ direction: "buy", foreignAmount: 500, rmTotal: 2103.4, mid: 4.056 });
    close(r.effectiveRate, 4.2068, 4);
    close(r.cost, 75.4);
    close(r.markupPct, 3.72);
    assert.equal(r.rating.label, "Expensive");
  });
});

describe("sanity checks", () => {
  test("slightly better than the real rate is allowed (daily movement)", () => {
    const r = analyse({ direction: "buy", foreignAmount: 100, rmTotal: 405.0, mid: 4.056 }); // -0.15%
    assert.ok(r.ok);
    assert.equal(r.cost, 0);
    assert.equal(r.rating.label, "Very good");
  });

  test("much better than the real rate is rejected", () => {
    const r = analyse({ direction: "buy", foreignAmount: 100, rmTotal: 380, mid: 4.056 });
    assert.equal(r.ok, false);
    assert.match(r.errors[0], /better than the real rate/);
  });

  test("picking the wrong direction is caught", () => {
    // Bank sells USD at 4.15, but the user picked "sell"
    const r = analyse({ direction: "sell", foreignAmount: 100, rmTotal: 415, mid: 4.056 });
    assert.equal(r.ok, false);
  });

  test("huge markup gives a warning but still a result", () => {
    const r = analyse({ direction: "buy", foreignAmount: 100, rmTotal: 500, mid: 4.056 });
    assert.ok(r.ok);
    assert.match(r.warnings[0], /unusually high/);
  });

  test("missing inputs list every problem", () => {
    const r = analyse({ direction: "buy", foreignAmount: 0, rmTotal: 0, mid: 0 });
    assert.equal(r.ok, false);
    assert.equal(r.errors.length, 3);
  });
});

describe("rating bands", () => {
  for (const [pct, label] of [
    [0, "Very good"],
    [0.49, "Very good"],
    [0.5, "Good"],
    [1.49, "Good"],
    [1.5, "Typical"],
    [2.99, "Typical"],
    [3, "Expensive"],
    [25, "Expensive"],
    [-0.3, "Very good"],
  ]) {
    test(`${pct}% is ${label}`, () => assert.equal(rate(pct).label, label));
  }
});

describe("reversed quotes", () => {
  test("'1 MYR = 0.2465 USD' is flipped to RM per USD", () => {
    close(suggestFlip(0.2465, 4.056), 4.0568, 4);
  });

  test("'1 MYR = 37.5 JPY' is flipped to RM per 100 JPY", () => {
    close(suggestFlip(37.5, 2.5644, 100), 2.6667, 4);
  });

  test("a normal quote is not flipped", () => {
    assert.equal(suggestFlip(4.15, 4.056), null);
  });

  test("a typo that is wrong both ways is not flipped", () => {
    assert.equal(suggestFlip(41.5, 4.056), null);
  });
});

describe("rate on a date", () => {
  const series = [
    { date: "2026-11-06", value: 4.1 },
    { date: "2026-11-07", value: 4.2 },
    { date: "2026-11-10", value: 4.3 },
  ];

  test("exact date", () => assert.equal(rateOn(series, "2026-11-07").value, 4.2));
  test("weekend uses the previous day", () => assert.equal(rateOn(series, "2026-11-09").value, 4.2));
  test("after the last date uses the latest", () => assert.equal(rateOn(series, "2026-12-01").value, 4.3));
  test("before the first date has no rate", () => assert.equal(rateOn(series, "2026-01-01"), null));
});
