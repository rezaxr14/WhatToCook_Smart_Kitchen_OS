/**
 * Non-blocking stylesheet loading without an inline `onload` handler.
 *
 * `index.html` marks the web-font stylesheet `media="print" data-async-style` so it never blocks first
 * paint, then flips it to `media="all"` once it has loaded. The classic `onload="this.media='all'"`
 * is an inline event handler, which our CSP (`script-src 'self'`, see nginx/csp-spa.conf) blocks, so the
 * swap lives here instead.
 */
export function activateAsyncStyles(root: ParentNode = document): void {
  root.querySelectorAll<HTMLLinkElement>('link[data-async-style]').forEach((link) => {
    const apply = () => {
      link.media = 'all';
    };
    // The sheet may already have finished loading before this module ran.
    if (link.sheet) apply();
    else link.addEventListener('load', apply, { once: true });
  });
}
