import React, { useEffect, useState } from 'react';

const PLACEHOLDER = '/placeholder.svg';

export interface SafeImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  /** Local (or API) image. */
  src?: string | null;
  /** Public fallback, used only when the local file is missing. */
  fallback?: string | null;
  /** Final bundled image; defaults to the local placeholder. */
  placeholder?: string;
  onError?: React.ReactEventHandler<HTMLImageElement>;
}

/**
 * Walks `[src, fallback, placeholder]` once and never loops: every stage is
 * compared before it is selected, so an image that fails back to itself cannot
 * re-trigger the error handler forever. Callers can keep passing `onError`
 * for analytics; it runs after the internal stage advance.
 */
export const SafeImage: React.FC<SafeImageProps> = ({
  src,
  fallback,
  placeholder = PLACEHOLDER,
  onError,
  alt,
  ...rest
}) => {
  const sources = [src, fallback, placeholder].filter(
    (value, index, list): value is string =>
      Boolean(value) && list.indexOf(value) === index,
  );
  const [stage, setStage] = useState(0);

  useEffect(() => {
    setStage(0);
  }, [src, fallback, placeholder]);

  const active = sources[Math.min(stage, sources.length - 1)] ?? PLACEHOLDER;

  return (
    <img
      {...rest}
      alt={alt}
      src={active}
      onError={(event) => {
        if (stage < sources.length - 1) {
          setStage((current) => Math.min(current + 1, sources.length - 1));
        }
        onError?.(event);
      }}
    />
  );
};
