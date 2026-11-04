/**
 * Unified API Client for WhatToCook
 */

import { requestChallenge } from '../lib/challenge';

function getCookie(name: string): string | null {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

export function getCsrfToken(): string | null {
  return getCookie('csrftoken');
}

/** Human readable countdown (e.g. "45s", "2 min"). */
export function formatRetryAfter(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))}s`;
  const m = Math.round(seconds / 60);
  return m >= 60 ? `${Math.round(m / 60)}h ${m % 60}m` : `${m} min`;
}

/**
 * Error thrown for any non-2xx API response. Carries machine-readable
 * fields so UI code can react to rate limits (HTTP 429) gracefully.
 */
export class ApiError extends Error {
  status: number;
  retryAfter: number | null;
  code: string | null;
  details: Record<string, unknown>;

  constructor(
    message: string,
    status: number,
    retryAfter: number | null = null,
    code: string | null = null,
    details: Record<string, unknown> = {}
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.retryAfter = retryAfter;
    this.code = code;
    this.details = details;
  }
}

interface ApiErrorPayload {
  error?: string;
  code?: string;
  detail?: string | Record<string, unknown>;
  message?: string;
  retry_after?: number;
  reset_at?: string;
  resets_at?: string;
  [key: string]: unknown;
}

/**
 * Auth endpoints carry their Turnstile token in the body, so the generic
 * step-up-and-retry loop must not pretend it can replay them.
 */
const CHALLENGE_RETRY_EXEMPT = [
  '/api/auth/login/',
  '/api/auth/signup/',
  '/api/auth/demo/',
  '/api/auth/challenge/',
];

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {},
  retried = false
): Promise<T> {
  const csrfToken = getCookie('csrftoken');

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(endpoint, {
    ...options,
    headers,
    credentials: 'include', // Ensure session cookies are sent
  });

  const contentType = response.headers.get('content-type');
  let data: unknown = null;

  if (contentType && contentType.includes('application/json')) {
    data = await response.json().catch(() => null);
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const payload: ApiErrorPayload =
      typeof data === 'object' && data !== null
        ? (data as ApiErrorPayload)
        : {};

    const code = (payload.code ?? payload.error ?? null) as string | null;
    const retryAfterHeader = response.headers.get('Retry-After');
    const retryAfter = payload?.retry_after ?? (retryAfterHeader ? Number(retryAfterHeader) : null);
    const isRateLimited = response.status === 429 || code === 'rate_limited';

    // Adaptive challenge: let the mounted gate verify the visitor once, then
    // replay the original request (the server counts the call again).
    if (
      code === 'challenge_required' &&
      !retried &&
      !CHALLENGE_RETRY_EXEMPT.some((path) => endpoint.startsWith(path))
    ) {
      const verified = await requestChallenge();
      if (verified) {
        return apiClient<T>(endpoint, options, true);
      }
    }

    let message: string;
    if (isRateLimited && retryAfter) {
      message = `You're moving fast! ⏳ Please wait ${formatRetryAfter(retryAfter)} before trying again.`;
    } else {
      const raw =
        (payload?.detail as string | undefined) ||
        (payload?.message as string | undefined) ||
        (payload?.error as string | undefined) ||
        `Request failed with status ${response.status}`;
      message = isRateLimited
        ? 'Too many requests — please slow down and try again shortly.'
        : typeof raw === 'string'
          ? raw
          : `Request failed with status ${response.status}`;
    }
    throw new ApiError(message, response.status, retryAfter, code, payload);
  }

  return data as T;
}
