// The other half of the load test: with rate limiting ON (the production default) a hammered scope must answer
// 429 + Retry-After + the JSON error body, THROUGH nginx. main.js runs with throttling off; this proves it still works
// when it is on. Run against a stack where THROTTLING_ENABLED is true (the load workflow flips it and recreates web).
//
//   k6 run -e BASE_URL=http://localhost:4173 load/k6/throttle.js
import http from "k6/http";
import { check } from "k6";

const BASE = (__ENV.BASE_URL || "http://localhost:4173").replace(/\/$/, "");

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: { checks: ["rate==1"] },
  userAgent: "wtc-k6-throttle/1",
};

export default function () {
  // `ai` is the tightest scope (GetFood/rate_limits.py); 60 attempts exceed any per-minute value it can be tuned to here.
  let limited = null;
  let first = null;
  for (let i = 0; i < 60 && !limited; i++) {
    const res = http.post(`${BASE}/api/ai/suggestions/`, JSON.stringify({ ingredients: ["egg", "tomato"], language: "en" }), {
      headers: { "Content-Type": "application/json" },
    });
    if (first === null) first = res;
    if (res.status === 429) limited = res;
  }
  check(first, { "requests under the limit are served": (r) => r.status === 200 });
  check(limited, {
    "the scope trips a 429": (r) => r !== null,
    "429 carries Retry-After": (r) => r !== null && Number(r.headers["Retry-After"]) > 0,
    "429 body is the documented JSON error": (r) => {
      if (r === null) return false;
      const b = r.json();
      return b.error === "rate_limited" && typeof b.retry_after === "number";
    },
  });
}
