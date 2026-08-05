const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const ACCESS_TOKEN_KEY = "access_token";
const USER_KEY = "auth_user";

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    if (response.status === 401 && !path.startsWith("/auth/")) {
      clearAccessToken();
      sessionStorage.setItem("post_login_redirect", `${window.location.pathname}${window.location.search}`);
      window.location.assign("/login");
    }
    throw new Error(error.detail ?? "Request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function setAccessToken(token: string) {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function setAuthenticatedUser(user: unknown) {
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getAuthenticatedUser<T>() {
  const value = sessionStorage.getItem(USER_KEY);
  return value ? (JSON.parse(value) as T) : null;
}

export function getAccessToken() {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function clearAccessToken() {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}
