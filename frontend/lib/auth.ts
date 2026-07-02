// Auth client: token storage + register/login/logout/me + history.

const TOKEN_KEY = "icare_token";

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function post(path: string, body: unknown): Promise<any> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export async function register(
  email: string,
  password: string,
  displayName: string
): Promise<AuthUser> {
  const d = await post("/api/auth/register", {
    email,
    password,
    display_name: displayName,
  });
  setToken(d.token);
  return d.user;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const d = await post("/api/auth/login", { email, password });
  setToken(d.token);
  return d.user;
}

export async function me(): Promise<AuthUser | null> {
  if (!getToken()) return null;
  const res = await fetch("/api/auth/me", { headers: authHeaders() });
  if (!res.ok) {
    clearToken();
    return null;
  }
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", {
    method: "POST",
    headers: authHeaders(),
  }).catch(() => {});
  clearToken();
}

export interface HistoryData {
  latest_conversation_id: number | null;
  latest_messages: { role: string; content: string }[];
}

export async function getHistory(): Promise<HistoryData> {
  const res = await fetch("/api/history", { headers: authHeaders() });
  if (!res.ok) return { latest_conversation_id: null, latest_messages: [] };
  return res.json();
}
