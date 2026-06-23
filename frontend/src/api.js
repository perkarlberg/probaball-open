// API client. In dev, base is "" and Vite proxies /api -> localhost:8080.
// In prod, set VITE_API_BASE to the Cloud Run service URL at build time.
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function req(path, opts) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const getCanonical = () => req("/api/canonical");
export const getMeta = () => req("/api/meta");
export const simulate = (payload) =>
  req("/api/simulate", { method: "POST", body: JSON.stringify(payload) });
export const rerollBracket = (payload) =>
  req("/api/sample-bracket", { method: "POST", body: JSON.stringify(payload) });
export const getHistory = () => req("/api/history");
