import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { Badge, IconButton } from '../components/primitives'
import { demoUser } from '../mock/data'

const primary = [
  ['/app', 'Command Center', '⌂'],
  ['/app/markets', 'Market Intelligence', '◎'],
  ['/app/trades', 'Trade Intelligence', '✦'],
  ['/app/performance', 'Performance Intelligence', '↗'],
]

const tools = ['Watchlists', 'Strategy Lab', 'Economic Calendar', 'News Intelligence', 'AI Reports', 'Journal & Coaching']
const system = ['Broker Connections', 'Settings', 'Notifications']
const ticker = ['BTC/USD 67,285.00 +1.72%', 'ETH/USD 3,452.21 +2.31%', 'EUR/USD 1.0886 +0.68%', 'GBP/USD 1.2734 -0.12%', 'NAS100 18,742.25 +0.35%', 'GOLD 2,341.52 +0.41%']

export const AppLayout = () => {
  const [open, setOpen] = useState(false)

  return (
    <div className={`app-shell ${open ? 'sidebar-open' : ''}`} data-testid="app-shell">
      <aside className="sidebar">
        <div className="sidebar__top">
          <Brand to="/app" />
          <IconButton label="Close navigation" onClick={() => setOpen(false)}>×</IconButton>
        </div>

        <nav aria-label="Primary navigation" className="nav-section">
          <span className="nav-label">Primary</span>
          {primary.map(([to, label, icon]) => (
            <NavLink end={to === '/app'} to={to} key={to}>
              <span className="nav-icon" aria-hidden="true">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="nav-section">
          <span className="nav-label">Workspace Tools</span>
          {tools.map((item) => <button type="button" key={item}>{item}</button>)}
        </div>

        <div className="nav-section">
          <span className="nav-label">Account & System</span>
          {system.map((item) => <button type="button" key={item}>{item}</button>)}
        </div>

        <div className="sidebar-status">
          <span>AI Authority</span>
          <strong>{demoUser.authority}</strong>
          <small>{demoUser.plan} Plan · You approve final decisions.</small>
          <button type="button">Ask AI Partner</button>
        </div>

        <div className="sidebar-status system-status">
          <span>System Status</span>
          <strong>All Systems Operational</strong>
          <small>Data delay: Real-Time · Latency: 18ms</small>
        </div>

        <div className="profile">
          <span className="avatar">CP</span>
          <div>
            <strong>{demoUser.firstName} {demoUser.lastName}</strong>
            <small>{demoUser.plan} Plan</small>
          </div>
        </div>
      </aside>

      <button className="sidebar-scrim" data-testid="sidebar-scrim" aria-label="Close navigation" onClick={() => setOpen(false)} />

      <section className="app-main" data-testid="app-main">
        <header className="utility-bar">
          <IconButton label="Open navigation" onClick={() => setOpen(true)}>☰</IconButton>
          <label className="global-search">
            <span aria-hidden="true">⌕</span>
            <input aria-label="Global search" placeholder="Search markets, assets, setups..." />
          </label>
          <div className="utility-status">
            <Badge tone="green">Markets Open</Badge>
            <span className="utility-time">08:52:15 ET</span>
            <IconButton label="Notifications">♢</IconButton>
            <IconButton label="Help">?</IconButton>
            <span className="avatar">CP</span>
          </div>
        </header>

        <main><Outlet /></main>

        <footer className="market-ticker" aria-label="Market ticker">
          <span>Market Ticker</span>
          {ticker.map((item) => <b key={item}>{item}</b>)}
        </footer>
      </section>
    </div>
  )
}
