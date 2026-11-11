/**
 * Hidden fee calculations — pure functions with no page or network code,
 * so they can be unit-tested in Node (see tests/fees.test.js).
 *
 * Conventions
 *   mid      real (mid-market) rate, in RM per 1 unit of foreign currency
 *   unit     display unit, e.g. 100 for JPY (rates shown as "RM per 100 JPY")
 *   'buy'    you pay RM and receive foreign currency
 *   'sell'   you give foreign currency and receive RM
 */

// Rough guidance, not an official standard. Upper bounds are in percent.
export const RATINGS = [
  { max: 0.5, label: "Very good", tone: "great", note: "Very close to the real rate." },
  { max: 1.5, label: "Good", tone: "good", note: "A fair deal." },
  { max: 3, label: "Typical", tone: "ok", note: "Normal for banks and cards. Cheaper options may exist." },
  { max: Infinity, label: "Expensive", tone: "bad", note: "A big markup. Compare other providers." },
];

// Daily rates move a little, so a quote slightly better than our reference is fine.
export const TOLERANCE_PCT = 0.5;
// Above this, the input is probably a typo.
export const SUSPICIOUS_PCT = 15;

export function rate(markupPct) {
  return RATINGS.find((r) => Math.max(markupPct, 0) < r.max);
}

/**
 * Total RM paid (buy) or received (sell) for a quoted rate plus a fixed fee.
 * quotedDisplay is in RM per `unit` foreign units, as shown on the rate board.
 */
export function rmTotalFromQuote({ direction, foreignAmount, quotedDisplay, unit = 1, fee = 0 }) {
  const rmBeforeFee = foreignAmount * (quotedDisplay / unit);
  return direction === "buy" ? rmBeforeFee + fee : rmBeforeFee - fee;
}

/**
 * Compare a deal with the real rate.
 * rmTotal: RM actually paid (buy) or received (sell), fees included.
 * Returns { ok: false, errors } or { ok: true, ...result, warnings }.
 */
export function analyse({ direction, foreignAmount, rmTotal, mid }) {
  const errors = [];
  if (direction !== "buy" && direction !== "sell") errors.push("Choose buying or selling.");
  if (!(foreignAmount > 0)) errors.push("Enter the foreign currency amount.");
  if (!(mid > 0)) errors.push("No real rate available for this date.");
  if (!(rmTotal > 0)) {
    errors.push(
      direction === "sell"
        ? "The amount you receive must be above zero. Is the fee bigger than the amount?"
        : "Enter the RM amount."
    );
  }
  if (errors.length) return { ok: false, errors };

  const fair = foreignAmount * mid; // RM at the real rate
  const cost = direction === "buy" ? rmTotal - fair : fair - rmTotal;
  const markupPct = (cost / fair) * 100;
  const warnings = [];

  if (markupPct < -TOLERANCE_PCT) {
    return {
      ok: false,
      errors: [
        "This is better than the real rate, which is very unlikely. Check the numbers, the date, " +
          "and whether you picked buying or selling correctly.",
      ],
    };
  }
  if (markupPct > SUSPICIOUS_PCT) {
    warnings.push(`A ${markupPct.toFixed(1)}% markup is unusually high. Double-check the numbers you entered.`);
  }

  return {
    ok: true,
    fair,
    actual: rmTotal,
    cost: Math.max(cost, 0),
    markupPct,
    effectiveRate: rmTotal / foreignAmount, // RM per 1 unit
    rating: rate(markupPct),
    warnings,
  };
}

/**
 * Some places quote the other way round ("1 MYR = 0.2465 USD").
 * If the entered number makes sense only when flipped, return the flipped
 * quote in RM per `unit` foreign units. Otherwise return null.
 */
export function suggestFlip(quotedDisplay, midDisplay, unit = 1) {
  if (!(quotedDisplay > 0) || !(midDisplay > 0)) return null;
  const off = (q) => Math.abs(q / midDisplay - 1) * 100;
  const flipped = unit / quotedDisplay;
  return off(quotedDisplay) > 50 && off(flipped) < SUSPICIOUS_PCT ? flipped : null;
}

/**
 * Find the real rate for a date in a sorted [{date, value}] series.
 * Weekends/holidays use the most recent earlier date.
 */
export function rateOn(series, date) {
  let found = null;
  for (const point of series) {
    if (point.date > date) break;
    found = point;
  }
  return found;
}
