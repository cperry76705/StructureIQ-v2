import { Outlet } from 'react-router-dom'

export const AuthLayout = () => (
  <div className="auth-shell">
    <main><Outlet /></main>
    <footer className="auth-footer">
      <span>Trusted & privacy-first</span>
      <span>Your data, your control</span>
      <span>Mandatory MFA</span>
      <span>Need help? Support</span>
    </footer>
  </div>
)
