interface PortalNavProps {
  clientName: string
}

export function PortalNav({ clientName }: PortalNavProps) {
  return (
    <nav className="nav">
      <div className="wordmark">
        <span className="wordmark-orpheus">Orpheus</span>
        <span className="wordmark-social">Social</span>
      </div>
      <div className="nav-client">
        <span className="nav-client-label">Confidential Portal for</span>
        <span className="nav-client-name">{clientName}</span>
      </div>
    </nav>
  )
}
