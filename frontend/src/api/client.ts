/**
 * Unified API Client for WhatToCook
 */

import i18n from '../i18n';

function currentLanguage(): string {
  return i18n.resolvedLanguage || i18n.language || 'en';
}

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

  constructor(message: string, status: number, retryAfter: number | null = null, code: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.retryAfter = retryAfter;
    this.code = code;
  }
}

interface ApiErrorPayload {
  error?: string;
  detail?: string | Record<string, unknown>;
  retry_after?: number;
}

export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const csrfToken = getCookie('csrftoken');

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    // The API returns `display_*` fields for this language; the canonical
    // English fields stay in place for matching and Telegram.
    'Accept-Language': currentLanguage(),
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

    const retryAfterHeader = response.headers.get('Retry-After');
    const retryAfter = payload?.retry_after ?? (retryAfterHeader ? Number(retryAfterHeader) : null);
    const isRateLimited = response.status === 429 || payload?.error === 'rate_limited';

    let message: string;
    if (isRateLimited && retryAfter) {
      message = `You're moving fast! ⏳ Please wait ${formatRetryAfter(retryAfter)} before trying again.`;
    } else {
      const raw =
        (payload?.detail as string | undefined) ||
        (payload?.error as string | undefined) ||
        `Request failed with status ${response.status}`;
      message = isRateLimited
        ? 'Too many requests — please slow down and try again shortly.'
        : typeof raw === 'string'
          ? raw
          : `Request failed with status ${response.status}`;
    }
    throw new ApiError(message, response.status, retryAfter, payload?.error ?? null);
  }

  return data as T;
}
