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

  let res;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers });
  } catch {
    throw Object.assign(new Error("Network error — is the API server running?"), { status: 0 });
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

export const api = {
  get: (path) => request(path),
  post: (path, body) =>
    request(path, { method: "POST", body: JSON.stringify(body) }),
  patch: (path, body) =>
    request(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: "DELETE" }),
};

export const setToken = (token) =>
  localStorage.setItem("narrative_token", token);
export const clearToken = () => localStorage.removeItem("narrative_token");
