import { Outlet } from 'react-router-dom'
import { PortalNav } from './PortalNav'
import { PortalFooter } from './PortalFooter'

/**
 * Shared shell for all authenticated client-portal screens.
 * Matches the `<nav> / <main> / <footer>` structure used across
 * the HTML prototypes in the repo root.
 *
 * PortalNav reads the signed-in user from the Supabase session itself
 * (see useSession in src/lib/auth.ts), so this layout doesn't pass any
 * client identity props.
 */
export function PortalLayout() {
  return (
    <>
      <PortalNav />
      <Outlet />
      <PortalFooter />
    </>
  )
}
