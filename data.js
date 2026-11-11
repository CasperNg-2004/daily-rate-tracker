/**
 * Shared data loading for the dashboard and the fee checker.
 * All rates are returned as RM per 1 unit of the foreign currency.
 */

export const API = "https://api.frankfurter.dev/v2/rates";

/** Load config.json -> { currencies: {USD: {name, unit}, ...}, codes: ["USD", ...] } */
export async function loadConfig() {
  const res = await fetch(`config.json?t=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`config.json: HTTP ${res.status}`);
  const cfg = await res.json();
  const currencies = cfg.currencies || {};
  for (const c in currencies) currencies[c].unit ||= 1;
  const codes = Object.keys(currencies);
  if (!codes.length) throw new Error("config.json has no currencies");
  return { currencies, codes };
}

/** Parse rates.csv text -> { USD: [{date, value}, ...sorted], ... } */
export function parseCSV(text) {
  const out = {};
  const lines = text.trim().split(/\r?\n/).slice(1);
  for (const line of lines) {
    const [date, cur, val] = line.split(",");
    const v = parseFloat(val);
    if (!date || !cur || !Number.isFinite(v)) continue;
    (out[cur] ||= []).push({ date, value: v });
  }
  for (const k in out) out[k].sort((a, b) => a.date.localeCompare(b.date));
  return out;
}

/** Saved history from data/rates.csv (empty object if it can't be loaded). */
export async function loadHistory() {
  try {
    const res = await fetch(`data/rates.csv?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    return parseCSV(await res.text());
  } catch (e) {
    console.warn("Could not load history CSV:", e);
    return {};
  }
}

/** Latest rates from the API -> { USD: {date, value}, ... }. Throws on failure. */
export async function fetchLive(codes) {
  const res = await fetch(`${API}?base=MYR&quotes=${codes.join(",")}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const rows = await res.json();
  const live = {};
  for (const r of rows) {
    if (codes.includes(r.quote) && r.rate > 0) live[r.quote] = { date: r.date, value: 1 / r.rate };
  }
  if (!Object.keys(live).length) throw new Error("empty response");
  return live;
}

/** Last saved value for each currency, used when the live API can't be reached. */
export function latestFromHistory(history, codes) {
  const out = {};
  for (const c of codes) {
    const h = history[c];
    if (h?.length) out[c] = { ...h[h.length - 1] };
  }
  return out;
}

/** Today's date in Malaysia time, as YYYY-MM-DD. */
export function todayMY() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kuala_Lumpur" }).format(new Date());
}
