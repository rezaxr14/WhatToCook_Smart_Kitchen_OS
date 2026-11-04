import { useState, useCallback, useRef } from 'react';
import i18n from '../i18n';
import { formatRetryAfter } from '../api/client';

interface UseAIStreamOptions {
  onChunk?: (chunk: string, accumulated: string) => void;
  onComplete?: (fullText: string) => void;
  onError?: (error: Error) => void;
}

export const useAIStream = (options?: UseAIStreamOptions) => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (recipeName: string, provider: string = 'gemini') => {
      setIsStreaming(true);
      setStreamedText('');
      setError(null);

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      try {
        const url = `/api/ai/stream/recipe/?recipe=${encodeURIComponent(recipeName)}&provider=${encodeURIComponent(provider)}&language=${encodeURIComponent(i18n.language)}`;
        const response = await fetch(url, {
          signal: abortControllerRef.current.signal,
          headers: {
            Accept: 'text/event-stream',
          },
        });

        if (!response.ok) {
          let message = `Stream request failed with status ${response.status}`;
          try {
            const body = await response.json();
            if (response.status === 429) {
              const wait = body?.retry_after ?? Number(response.headers.get('Retry-After')) ?? 30;
              message = `You're moving fast! ⏳ Please wait ${formatRetryAfter(wait)} before trying again.`;
            } else if (typeof body?.detail === 'string') {
              message = body.detail;
            }
          } catch {
            /* non-JSON error body — keep default message */
          }
          throw new Error(message);
        }

        if (!response.body) {
          throw new Error('ReadableStream not supported on this browser.');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulated = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const textChunk = decoder.decode(value, { stream: true });
          const lines = textChunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const jsonStr = line.replace('data: ', '').trim();
              if (!jsonStr) continue;

              let parsed: { chunk?: string; done?: boolean; error?: string; message?: string } | null = null;
              try {
                parsed = JSON.parse(jsonStr);
              } catch {
                // If not JSON, treat raw
                accumulated += jsonStr;
                setStreamedText(accumulated);
                continue;
              }

              if (parsed?.error) {
                throw new Error(parsed.message || 'Stream generation failed');
              }
              if (parsed?.chunk) {
                accumulated += parsed.chunk;
                setStreamedText(accumulated);
                options?.onChunk?.(parsed.chunk, accumulated);
              }
              if (parsed?.done) {
                break;
              }
            }
          }
        }

        options?.onComplete?.(accumulated);
      } catch (err: any) {
        if (err.name === 'AbortError') return;
        const errMsg = err.message || 'Stream generation failed';
        setError(errMsg);
        options?.onError?.(err);
      } finally {
        setIsStreaming(false);
      }
    },
    [options]
  );

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  return {
    isStreaming,
    streamedText,
    error,
    startStream,
    stopStream,
  };
};
