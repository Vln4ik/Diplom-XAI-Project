const ACCESS_TOKEN_KEY = "xai-access-token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}
