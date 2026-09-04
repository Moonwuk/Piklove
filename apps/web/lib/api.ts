const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message?: string) {
    super(message || code);
    this.code = code;
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${base}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    let code = 'UNKNOWN_ERROR';
    let message = `HTTP ${r.status}`;
    try {
      const j = await r.json();
      const err = j?.error ?? j;
      if (typeof err === 'string') code = err;
      else if (err?.code) {
        code = typeof err.code === 'string' ? err.code : 'QUOTA_EXCEEDED';
        message = err.message ?? message;
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(r.status, code, message);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}