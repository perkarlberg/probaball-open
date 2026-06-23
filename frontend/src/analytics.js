// Thin wrapper around GA4 gtag. No-ops if the tag isn't loaded (e.g. blocked).
export function track(event, params = {}) {
  if (typeof window !== "undefined" && typeof window.gtag === "function") {
    window.gtag("event", event, params);
  }
}
