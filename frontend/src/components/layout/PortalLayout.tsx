import { Outlet } from 'react-router-dom'
import { PortalNav } from './PortalNav'
import { PortalFooter } from './PortalFooter'

/**
 * Shared shell for all authenticated client-portal screens.
 * Matches the `<nav> / <main> / <footer>` structure used across
 * the HTML prototypes in the repo root.
 */
export function PortalLayout() {
  return (
    <>
      <PortalNav clientName="Jane Doe" />
      <Outlet />
      <PortalFooter />
    </>
  )
}
