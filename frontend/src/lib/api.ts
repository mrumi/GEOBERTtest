// ============================================================
// lib/api.ts — Typed API Client
// ============================================================
// Thin wrapper around fetch() for every backend endpoint we
// built in api/routes/*.py. Centralizing this here means the
// base URL and auth header logic exist in exactly one place.

import { getToken } from "./auth-store";
import type {
  QueryResponse,
  SessionSummary,
  SessionDetail,
  DatasetDetail,
  TokenResponse,
  RegisterPayload,
  RegisterResponse,
  LoginPayload,
  UserOut,
  MessageResponse,
  ResetPasswordPayload,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (authenticated) {
    const token = getToken();
    if (!token) {
      throw new ApiError(
        401,
        "No auth token set — paste one from /docs (see the dev token bar)."
      );
    }
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON — keep statusText
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content etc.
  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

// ============================================================
// Auth
// ============================================================

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  return apiFetch<TokenResponse>(
    "/auth/login",
    { method: "POST", body: JSON.stringify(payload) },
    false
  );
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>(
    "/auth/register",
    { method: "POST", body: JSON.stringify(payload) },
    false
  );
}

export async function verifyEmail(token: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(
    "/auth/verify-email",
    { method: "POST", body: JSON.stringify({ token }) },
    false
  );
}

export async function resendVerification(email: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(
    "/auth/resend-verification",
    { method: "POST", body: JSON.stringify({ email }) },
    false
  );
}

export async function forgotPassword(email: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(
    "/auth/forgot-password",
    { method: "POST", body: JSON.stringify({ email }) },
    false
  );
}

export async function resetPassword(payload: ResetPasswordPayload): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(
    "/auth/reset-password",
    { method: "POST", body: JSON.stringify(payload) },
    false
  );
}

export async function getMe(): Promise<UserOut> {
  return apiFetch<UserOut>("/auth/me");
}

// ============================================================
// Query
// ============================================================

export async function runQuery(
  query: string,
  sessionId: string | null
): Promise<QueryResponse> {
  return apiFetch<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify({ query, session_id: sessionId }),
  });
}

// ============================================================
// Sessions
// ============================================================

export async function listSessions(): Promise<SessionSummary[]> {
  return apiFetch<SessionSummary[]>("/sessions");
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return apiFetch<SessionDetail>(`/sessions/${sessionId}`);
}

export async function createSession(): Promise<SessionSummary> {
  return apiFetch<SessionSummary>("/sessions", { method: "POST" });
}

export async function deleteSession(sessionId: string): Promise<void> {
  return apiFetch<void>(`/sessions/${sessionId}`, { method: "DELETE" });
}

// ============================================================
// Datasets
// ============================================================

export async function getDatasetDetail(gseId: string): Promise<DatasetDetail> {
  return apiFetch<DatasetDetail>(`/datasets/${gseId}`);
}
