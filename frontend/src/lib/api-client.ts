const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8200";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const resp = await fetch(url, { ...options, headers });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body.detail || resp.statusText);
  }

  if (resp.status === 204) return undefined as T;
  return resp.json();
}
