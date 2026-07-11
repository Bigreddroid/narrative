const BASE = "/api/v1";

function getToken() {
  return localStorage.getItem("narrative_token");
}

async function safeJson(res) {
  const text = await res.text().catch(() => "");
  if (!text) return null;
  try { return JSON.parse(text); } catch { return null; }
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  // Fail fast if the backend is unreachable so offline mock fallbacks kick in
  // quickly (a dead proxy target can otherwise hang the request for ~minutes).
  // Default 3.5s fail-fast for normal REST, but callers can override (e.g. the
  // LLM analyst chat needs much longer — a cold local model can take 10–30s).
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), options.timeoutMs ?? 3500);

  let res;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers, signal: ctrl.signal });
  } catch {
    throw Object.assign(new Error("Network error — is the API server running?"), { status: 0 });
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const data = await safeJson(res);
    throw Object.assign(
      new Error(data?.detail || res.statusText || "Request failed"),
      { status: res.status }
    );
  }

  return safeJson(res);
}

// Multipart upload (e.g. image geolocation). Never set Content-Type — the browser
// must add the multipart boundary itself. Long default timeout: a cold vision model
// can take 20-60s. Auth header is attached like the JSON path.
async function postForm(path, formData, { timeoutMs = 60000 } = {}) {
  const token = getToken();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      body: formData,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: ctrl.signal,
    });
  } catch {
    throw Object.assign(new Error("Network error — is the API server running?"), { status: 0 });
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    const data = await safeJson(res);
    throw Object.assign(new Error(data?.detail || res.statusText || "Upload failed"), { status: res.status });
  }
  return safeJson(res);
}

export const api = {
  get: (path) => request(path),
  post: (path, body, opts = {}) =>
    request(path, { method: "POST", body: JSON.stringify(body), ...opts }),
  postForm,
  patch: (path, body) =>
    request(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: "DELETE" }),
};

export const setToken = (token) =>
  localStorage.setItem("narrative_token", token);
export const clearToken = () => localStorage.removeItem("narrative_token");
