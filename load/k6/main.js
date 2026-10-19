// WhatToCook load / soak test (k6). Run it against a stack with THROTTLING_ENABLED=false and an EMPTY GEMINI_API_KEY
// (see .github/workflows/load.yml and README "Load & soak"): the point is to measure the app, not the rate limiter,
// and never to spend real LLM quota.
//
//   k6 run -e BASE_URL=http://localhost:4173 -e INCLUDE_SPA=true load/k6/main.js        # nightly profile (~12 min)
//   k6 run -e PROFILE=smoke -e BASE_URL=http://127.0.0.1:8000 load/k6/main.js            # 25 s, scripts + thresholds
//
// Environment: BASE_URL, PROFILE=soak|smoke (default soak), STEADY (default 10m), RAMP (default 1m),
//              INCLUDE_SPA=true (also fetch the SPA shell and assert its security headers; needs nginx in front).
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const BASE = (__ENV.BASE_URL || "http://localhost:4173").replace(/\/$/, "");
const SMOKE = (__ENV.PROFILE || "soak") === "smoke";
const SPA = (__ENV.INCLUDE_SPA || "false") === "true";
const STEADY = __ENV.STEADY || "10m";
const RAMP = __ENV.RAMP || "1m";

// Iterations per second at steady state (each iteration is 1-4 requests). Sized for a 2-vCPU CI runner running the
// whole compose stack; raise them on bigger hardware.
const RATES = { browse: 5, can_cook: 3, shopping: 2, ai: 2, spa: 2 };

// A shopping-list read that contains somebody else's item is a data leak (AGENTS.md: shopping lists are owner-scoped).
const isolationViolations = new Counter("isolation_violations");

function stages(rate) {
  const r = SMOKE ? Math.max(1, Math.round(rate / 2)) : rate;
  return SMOKE
    ? [{ duration: "5s", target: r }, { duration: "15s", target: r }, { duration: "5s", target: 0 }]
    : [{ duration: RAMP, target: r }, { duration: STEADY, target: r }, { duration: "30s", target: 0 }];
}

function scenario(name, exec, rate) {
  return {
    executor: "ramping-arrival-rate",
    exec,
    startRate: 1,
    timeUnit: "1s",
    stages: stages(rate),
    preAllocatedVUs: Math.max(5, rate * 3),
    maxVUs: Math.max(40, rate * 20),
    tags: { scenario_name: name },
  };
}

const scenarios = {
  browse: scenario("browse", "browse", RATES.browse),
  can_cook: scenario("can_cook", "canCook", RATES.can_cook),
  shopping: scenario("shopping", "shopping", RATES.shopping),
  ai: scenario("ai", "ai", RATES.ai),
};
if (SPA) scenarios.spa = scenario("spa", "spa", RATES.spa);

const thresholds = {
  http_req_failed: ["rate<0.01"],
  checks: ["rate>0.99"],
  "http_req_duration{endpoint:catalog}": ["p(95)<500"],
  "http_req_duration{endpoint:stats}": ["p(95)<500"],
  "http_req_duration{endpoint:can_cook}": ["p(95)<1500"],
  "http_req_duration{endpoint:shopping}": ["p(95)<800"],
  "http_req_duration{endpoint:ai_suggestions}": ["p(95)<2000"],
  // Offered load that was not delivered means the system saturated: the run is not a valid measurement.
  dropped_iterations: ["count<10"],
  isolation_violations: ["count==0"],
};
if (SPA) thresholds["http_req_duration{endpoint:spa}"] = ["p(95)<500"];

export const options = { scenarios, thresholds, noConnectionReuse: false, userAgent: "wtc-k6-load/1" };

const JSON_HEADERS = { "Content-Type": "application/json" };
const PANTRY = ["egg", "tomato", "garlic", "onion", "rice", "chicken", "basil", "lemon", "potato", "cheese", "pasta", "mushroom"];

function get(path, endpoint) {
  return http.get(`${BASE}${path}`, { tags: { endpoint } });
}

function post(path, body, endpoint) {
  return http.post(`${BASE}${path}`, JSON.stringify(body), { headers: JSON_HEADERS, tags: { endpoint } });
}

function json(res) {
  try {
    return res.json();
  } catch (e) {
    return null;
  }
}

export function browse() {
  const recipes = get("/api/recipes/", "catalog");
  check(recipes, { "recipes 200": (r) => r.status === 200, "recipes is a non-empty list": (r) => { const b = json(r); return Array.isArray(b) && b.length > 0; } });
  const ingredients = get("/api/ingredients/", "catalog");
  check(ingredients, { "ingredients 200": (r) => r.status === 200 });
  const stats = get("/api/stats/", "stats");
  check(stats, { "stats 200": (r) => r.status === 200, "stats has totals": (r) => { const b = json(r); return !!b && typeof b.total_recipes === "number"; } });
}

export function canCook() {
  const res = get("/api/can-cook/", "can_cook");
  check(res, { "can-cook 200": (r) => r.status === 200, "can-cook has matches": (r) => { const b = json(r); return !!b && "full_matches" in b && "partial_matches" in b; } });
}

// One anonymous session per VU (k6 keeps a cookie jar per VU): add, read back, and clear its own list.
export function shopping() {
  const mine = `k6-vu${__VU}-`;
  const add = post("/api/shopping-list/add/", { name: `${mine}${__ITER}`, quantity: "1 item" }, "shopping");
  check(add, { "shopping add 200": (r) => r.status === 200, "shopping add succeeded": (r) => { const b = json(r); return !!b && b.status === "success"; } });
  const list = get("/api/shopping-list/", "shopping");
  const body = json(list);
  check(list, { "shopping list 200": (r) => r.status === 200, "shopping list holds my item": () => !!body && body.count >= 1 });
  const foreign = ((body && body.items) || []).filter((i) => !String(i.name).startsWith(mine));
  if (foreign.length > 0) isolationViolations.add(foreign.length);
  const clear = http.del(`${BASE}/api/shopping-list/clear/`, null, { tags: { endpoint: "shopping" } });
  check(clear, { "shopping clear 200": (r) => r.status === 200 });
}

// Inline AI path with an empty provider key: the provider fails instantly and the deterministic fallback answers.
export function ai() {
  const picks = [0, 1, 2].map(() => PANTRY[Math.floor(Math.random() * PANTRY.length)]);
  const res = post("/api/ai/suggestions/", { ingredients: picks, language: "en" }, "ai_suggestions");
  check(res, {
    "ai 200": (r) => r.status === 200,
    "ai answered with recipes": (r) => { const b = json(r); return !!b && (b.status === "done" ? Array.isArray(b.recipes) && b.recipes.length > 0 : b.status === "processing"); },
  });
}

export function spa() {
  const res = get("/", "spa");
  check(res, {
    "spa 200": (r) => r.status === 200,
    "spa sends a CSP": (r) => !!r.headers["Content-Security-Policy"],
    "spa sends nosniff": (r) => (r.headers["X-Content-Type-Options"] || "").toLowerCase() === "nosniff",
  });
}
