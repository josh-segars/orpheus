import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main className="main-interior">
      <div className="section-header">
        <div className="section-eyebrow">404</div>
        <h2 className="section-title">That page isn&rsquo;t here</h2>
        <p className="section-intro">
          The link you followed may be broken, or the page may have been moved.
        </p>
      </div>
      <div className="actions">
        <Link to="/jobs/demo" className="btn-primary">
          Return to your Signal Score
        </Link>
      </div>
    </main>
  )
}
