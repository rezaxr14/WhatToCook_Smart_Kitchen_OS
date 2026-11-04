import { ApiError, formatRetryAfter } from '../api/client';

type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * Turn a gateway/API error code into a localized, actionable message.
 *
 * Blocking codes (challenge, quota, pool, budget) are deliberately distinct:
 * retrying immediately cannot help, while `rate_limited` includes the wait.
 */
export function aiErrorMessage(err: unknown, t: Translate): string {
  if (err instanceof ApiError && err.code) {
    switch (err.code) {
      case 'challenge_required':
        return t('aiErrors.challenge');
      case 'quota_exceeded':
        return t('aiErrors.quota');
      case 'ai_pool_exhausted':
        return t('aiErrors.pool');
      case 'rate_limited':
        return t('aiErrors.rate', {
          wait: formatRetryAfter(err.retryAfter ?? 30),
        });
      case 'ai_disabled':
        return t('aiErrors.disabled');
      case 'ai_budget_exhausted':
        return t('aiErrors.budget');
      default:
        break;
    }
  }
  if (err instanceof Error && err.message) return err.message;
  return t('aiErrors.disabled');
}
