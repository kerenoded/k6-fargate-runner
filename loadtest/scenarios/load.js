import { check, sleep } from "k6";
import http from "k6/http";
import { buildHeaders } from "../utils/headers.js";

function loadRequestConfig() {
  if (__ENV.REQUEST_JSON) {
    return JSON.parse(__ENV.REQUEST_JSON);
  }

  const p = __ENV.REQUEST_FILE_PATH || "utils/request.json";
  return JSON.parse(open(p));
}

const REQUEST = loadRequestConfig();
const URL = REQUEST.url || __ENV.TARGET_URL;

// Load shape
function parseDurationSeconds(s) {
  if (s === undefined || s === null) return 0;
  const str = String(s).trim();
  if (str === "") return 0;

  // Accept formats like: 10s, 2m, 1h, 1d (and also bare numbers as seconds)
  const m = str.match(/^\s*(\d+)\s*([smhd])?\s*$/i);
  if (!m) {
    throw new Error(`Invalid duration '${str}'. Use formats like 30s, 2m, 1h, 1d.`);
  }
  const n = Number(m[1]);
  const unit = (m[2] || "s").toLowerCase();
  const mult = { s: 1, m: 60, h: 3600, d: 86400 }[unit];
  return n * mult;
}

// If WARMUP_* env vars are not provided, default warmup to disabled.
const WARMUP_VUS = __ENV.WARMUP_VUS ? Number(__ENV.WARMUP_VUS) : 0;
const WARMUP_DURATION = __ENV.WARMUP_DURATION ? String(__ENV.WARMUP_DURATION) : "0s";
const WARMUP_DURATION_SECONDS = parseDurationSeconds(WARMUP_DURATION);
const WARMUP_ENABLED = WARMUP_VUS > 0 && WARMUP_DURATION_SECONDS > 0;

const MEASURE_VUS = Number(__ENV.MEASURE_VUS || 50);
const MEASURE_DURATION = __ENV.MEASURE_DURATION || "2m";

// One request = one iteration
function doRequest() {
  const sleepMs = Number(__ENV.SLEEP_MS || 0);
  const method = String(REQUEST.method || __ENV.REQUEST_METHOD || "GET").toUpperCase();
  const body = REQUEST.body ?? __ENV.REQUEST_BODY;

  const requestHeaders =
    REQUEST && typeof REQUEST.headers === "object" && REQUEST.headers !== null && !Array.isArray(REQUEST.headers)
      ? REQUEST.headers
      : {};
  // request.json headers first, then env-based auth headers override on conflicts
  const headers = Object.assign({}, requestHeaders, buildHeaders());

  const bodyAllowed = method === "POST" || method === "PUT" || method === "PATCH";
  const bodyToSend = bodyAllowed ? (typeof body === "string" ? body : JSON.stringify(body)) : null;

  const res = http.request(method, URL, bodyToSend, { headers });
  check(res, { "status is 2xx/3xx": (r) => r.status >= 200 && r.status < 400 });

  if (sleepMs > 0) {
    sleep(sleepMs / 1000);
  }
}

// Thresholds are configurable via env vars so that slow or degraded APIs don't
// suppress the S3 result upload. When k6 breaches a threshold it exits with
// code 99, and the entrypoint skips the upload — losing the data you most want.
//
// Override defaults at runtime via run_task.py flags:
//   --threshold-error-rate 0.05   (default: 0.01 → 1%)
//   --threshold-p95-ms 2000       (default: 1000 → 1 s)
//
// Set either to "off" to disable that threshold entirely (always upload results).
const THRESHOLD_ERROR_RATE = __ENV.THRESHOLD_ERROR_RATE || "0.01";
const THRESHOLD_P95_MS = __ENV.THRESHOLD_P95_MS || "1000";

function buildThresholds() {
  const t = {};
  if (THRESHOLD_ERROR_RATE !== "off") {
    t["http_req_failed{scenario:measure}"] = [`rate<${THRESHOLD_ERROR_RATE}`];
  }
  if (THRESHOLD_P95_MS !== "off") {
    t["http_req_duration{scenario:measure}"] = [`p(95)<${THRESHOLD_P95_MS}`];
  }
  return t;
}

export const options = {
  discardResponseBodies: true,
  scenarios: Object.assign(
    {},
    WARMUP_ENABLED
      ? {
          warmup: {
            executor: "constant-vus",
            vus: WARMUP_VUS,
            duration: WARMUP_DURATION,
            exec: "warmupExec",
            tags: { phase: "warmup" },
          },
        }
      : {},
    {
      measure: {
        executor: "constant-vus",
        vus: MEASURE_VUS,
        duration: MEASURE_DURATION,
        exec: "measureExec",
        startTime: WARMUP_ENABLED ? WARMUP_DURATION : "0s",
        tags: { phase: "measure" },
      },
    }
  ),

  // Thresholds: tune via --threshold-error-rate / --threshold-p95-ms flags,
  // or set to "off" to disable. See comment above buildThresholds().
  thresholds: buildThresholds(),
};

export function warmupExec() {
  doRequest();
}

export function measureExec() {
  doRequest();
}

export function handleSummary(data) {
  const runId = __ENV.RUN_ID || "unknown";
  const targetUrl = __ENV.TARGET_URL || "unknown";
  const methodType = __ENV.REQUEST_METHOD || "unknown";

  const dur = data.metrics["http_req_duration{scenario:measure}"] || data.metrics["http_req_duration"];
  const fail = data.metrics["http_req_failed{scenario:measure}"] || data.metrics["http_req_failed"];
  const reqs = data.metrics["http_reqs{scenario:measure}"] || data.metrics["http_reqs"];

  const dv = dur?.values || {};
  const fv = fail?.values || {};
  const rv = reqs?.values || {};

  const ms = (x) => (x === undefined ? "-" : `${Number(x).toFixed(2)}ms`);
  const pct = (x) => (x === undefined ? "-" : `${(Number(x) * 100).toFixed(2)}%`);
  const num = (x) => (x === undefined ? "-" : `${Math.round(Number(x))}`);
  const rps = (x) => (x === undefined ? "-" : `${Number(x).toFixed(2)}`);

  const out =
    `RUN_ID=${runId} TARGET_URL=${targetUrl} REQUEST_METHOD=${methodType}
=== K6 SUMMARY (measure only) ===
Requests:   ${num(rv.count)} (${rps(rv.rate)} req/s)
Error rate: ${pct(fv.rate)}
Latency:
  avg: ${ms(dv.avg)}  p90: ${ms(dv["p(90)"])}  p95: ${ms(dv["p(95)"])}
  min: ${ms(dv.min)}  med: ${ms(dv.med)}  max: ${ms(dv.max)}
=================================
`;

  return {
    stdout: out,
    "/tmp/summary.json": JSON.stringify({
      run_id: runId,
      target_url: targetUrl,
      method_type: methodType,
      scenario: "load",
      ts: new Date().toISOString(),
      k6: data
    }),
  };
}