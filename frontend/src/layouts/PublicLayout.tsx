import { NavLink, Outlet } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { Button } from '../components/primitives'

export const PublicLayout = () => (
  <div className="public-shell">
    <header className="public-header">
      <Brand />
      <nav aria-label="Public navigation">
        <a href="/#platform">Platform</a>
        <a href="/#how">How It Works</a>
        <a href="/#features">Features</a>
        <NavLink to="/pricing">Pricing</NavLink>
        <a href="/#resources">Resources</a>
        <a href="/#company">Company</a>
      </nav>
      <div className="header-actions">
        <NavLink to="/signin"><Button variant="secondary">Log In</Button></NavLink>
        <NavLink to="/evaluation/create-account"><Button>Start 14-Day Guided Evaluation</Button></NavLink>
      </div>
    </header>
    <main><Outlet /></main>
    <footer className="public-footer">
      <Brand />
      <p>AI trading intelligence for disciplined decisions.</p>
      <nav>
        <a href="#privacy">Privacy</a>
        <a href="#terms">Terms</a>
        <a href="#security">Security</a>
      </nav>
      <small>© 2026 StructureIQ. Educational decision support; not a promise of outcomes.</small>
    </footer>
  </div>
)
