export function buildHeaders() {
  const h = {};

  if (__ENV.TARGET_API_KEY) h["x-api-key"] = __ENV.TARGET_API_KEY;
  if (__ENV.TARGET_BEARER_TOKEN) h["Authorization"] = `Bearer ${__ENV.TARGET_BEARER_TOKEN}`;

  return h;
}