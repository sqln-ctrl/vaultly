export type User = {
  id: string; email: string; full_name: string; email_verified: boolean; timezone: string; currency: string;
};
type AuthOut = { access_token: string; user: User };
type Opts = Omit<RequestInit, "body"> & { json?: unknown };

let accessToken: string | null = null;

export async function refreshSession(): Promise<User | null> {
  const res = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include" });
  if (!res.ok) { accessToken = null; return null; }
  const data: AuthOut = await res.json();
  accessToken = data.access_token;
  return data.user;
}

export async function api<T = void>(path: string, opts: Opts = {}, retry = true): Promise<T> {
  const headers = new Headers(opts.headers);
  let body: string | undefined;
  if (opts.json !== undefined) { headers.set("Content-Type", "application/json"); body = JSON.stringify(opts.json); }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const res = await fetch(`/api/v1${path}`, { ...opts, body, headers, credentials: "include" });
  if (res.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, opts, false);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    const detail = err?.detail;
    throw new Error(typeof detail === "string" ? detail : "Something went wrong. Try again.");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const setAccessToken = (t: string | null) => { accessToken = t; };
