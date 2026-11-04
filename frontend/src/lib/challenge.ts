/**
 * Bridge between the API client and the challenge modal.
 *
 * `apiClient` cannot import a React component, so the mounted `ChallengeGate`
 * registers a handler here. When any AI request comes back with
 * `challenge_required`, the client awaits this handler and retries the request
 * once after the visitor proves they are human.
 */

export type ChallengeHandler = () => Promise<boolean>;

let handler: ChallengeHandler | null = null;

export function registerChallengeHandler(next: ChallengeHandler): () => void {
  handler = next;
  return () => {
    if (handler === next) handler = null;
  };
}

export function hasChallengeHandler(): boolean {
  return handler !== null;
}

export async function requestChallenge(): Promise<boolean> {
  if (!handler) return false;
  try {
    return await handler();
  } catch {
    return false;
  }
}
