const configuredApiUrl = process.env.REACT_APP_API_URL || process.env.REACT_APP_API_BASE_URL;
const API_BASE_URL = configuredApiUrl
  ? configuredApiUrl.replace(/\/api\/?$/, "")
  : "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event("obrail:unauthorized"));
    throw new Error(`Erreur API ${response.status} sur ${path}`);
  }

  return response.json();
}

export function getInternalOverview() {
  return request("/api/internal/overview");
}

export function runInternalDiagnostic() {
  return request("/api/internal/diagnostic/run", { method: "POST" });
}

export function runInternalTests() {
  return request("/api/internal/tests/run", { method: "POST" });
}

export function streamInternalTests(onMessage, onError, onDone) {
  const streamUrl = `${API_BASE_URL}/api/internal/tests/stream`;
  const source = new EventSource(streamUrl, { withCredentials: true });
  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      onMessage?.(payload);
      if (payload.kind === "done") {
        source.close();
        onDone?.();
      }
    } catch (err) {
      onError?.(err);
    }
  };
  source.onerror = (err) => {
    source.close();
    onError?.(err);
  };
  return source;
}

export function streamInternalTestsCategory(category, onMessage, onError, onDone) {
  const streamUrl = `${API_BASE_URL}/api/internal/tests/stream/${category}`;
  const source = new EventSource(streamUrl, { withCredentials: true });
  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      onMessage?.(payload);
      if (payload.kind === "done") {
        source.close();
        onDone?.(payload);
      }
    } catch (err) {
      onError?.(err);
    }
  };
  source.onerror = (err) => {
    source.close();
    onError?.(err);
  };
  return source;
}
