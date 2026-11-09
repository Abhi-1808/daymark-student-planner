export async function requestJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error("The server is unavailable. Check your connection and try again.");
  }

  if (response.status === 204) return null;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((error) => error.msg).filter(Boolean).join("; ")
      : typeof detail === "string" ? detail : typeof detail?.message === "string" ? detail.message : "";
    const error = new Error(message || `The request failed (${response.status}). Please try again.`);
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  if (body === null) throw new Error("The server returned an invalid response. Please try again.");
  return body;
}
