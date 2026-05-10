const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public body: string, public url: string) {
    super(`API ${status}: ${url}`);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  adminToken?: string;
  signal?: AbortSignal;
  /** When true, treat 404 as a real error rather than returning null. */
  throwOn404?: boolean;
}

async function request<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<T | null> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.adminToken) headers.Authorization = `Bearer ${opts.adminToken}`;

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: opts.signal,
  });

  if (res.status === 404 && !opts.throwOn404) return null;

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text, `${BASE_URL}${path}`);
  }

  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return null;
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(path: string, opts?: RequestOptions) => request<T>("GET", path, undefined, opts),
  post: <T,>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("POST", path, body, opts),
  delete: <T,>(path: string, opts?: RequestOptions) => request<T>("DELETE", path, undefined, opts),
};
