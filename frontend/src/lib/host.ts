/**
 * Hostname routing for the single Vercel deployment that serves both the
 * marketing site and the product app (ORPHEUS-8).
 *
 * The same Vite bundle is attached to two domains:
 *   - www.orpheussocial.com / orpheussocial.com (apex) → marketing landing page
 *   - app.orpheussocial.com                            → the product portal
 *
 * `isMarketingHost()` decides which tree App.tsx renders. Apex and www are
 * marketing; everything else (app.*, preview deploys, localhost) is the app.
 *
 * Local preview: the app tree also exposes the landing page at `/site` so it
 * can be viewed on localhost without spoofing a hostname.
 */
export function isMarketingHost(): boolean {
  if (typeof window === 'undefined') return false
  const host = window.location.hostname.toLowerCase()
  return host === 'orpheussocial.com' || host === 'www.orpheussocial.com'
}
