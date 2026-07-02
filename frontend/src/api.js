const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function buildUrl(path) {
  const cleanBaseUrl = API_BASE_URL.replace(/\/$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  return `${cleanBaseUrl}${cleanPath}`;
}

function getHeaders(apiKey) {
  const headers = {
    "Content-Type": "application/json",
  };

  if (apiKey) {
    headers["x-api-key"] = apiKey;
  }

  return headers;
}

async function parseResponse(response) {
  const text = await response.text();

  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = {
      raw: text,
    };
  }

  if (!response.ok) {
    const message =
      data?.message ||
      data?.detail ||
      `Request failed with status ${response.status}`;

    const error = new Error(message);
    error.status = response.status;
    error.data = data;

    throw error;
  }

  return data;
}

export async function apiGet(path, apiKey) {
  const response = await fetch(buildUrl(path), {
    method: "GET",
    headers: getHeaders(apiKey),
  });

  return parseResponse(response);
}

export async function apiPost(path, body, apiKey) {
  const response = await fetch(buildUrl(path), {
    method: "POST",
    headers: getHeaders(apiKey),
    body: JSON.stringify(body || {}),
  });

  return parseResponse(response);
}

export function getApiBaseUrl() {
  return API_BASE_URL;
}