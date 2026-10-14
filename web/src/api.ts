export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Não foi possível concluir a operação (${response.status}).`;
    try {
      const error = await response.json();
      message =
        typeof error.detail === "string"
          ? error.detail
          : (error.detail?.[0]?.msg ?? message);
    } catch {
      /* Keep the HTTP status when the server cannot return JSON. */
    }
    throw new Error(message);
  }
  return response.json();
}
export const fileUrl = (jobId: string, name: string, download = false) =>
  `/api/jobs/${jobId}/files/${name}${download ? "?download=true" : ""}`;
