import { Link, Outlet, useLocation } from 'react-router-dom'
import { Brand } from '../components/Brand'
import { ProgressIndicator } from '../components/primitives'

const steps = ['/evaluation/create-account', '/evaluation/payment', '/evaluation/verify', '/evaluation/welcome']

export const WizardLayout = () => {
  const { pathname } = useLocation()
  const step = Math.max(1, steps.indexOf(pathname) + 1)

  return (
    <div className="wizard-shell">
      <header>
        <Brand />
        <div className="wizard-secure">
          <span>▣ Secure 256-bit Encryption</span>
          <a href="mailto:support@structureiq.example">Need help? Contact Support</a>
        </div>
      </header>
      <Link className="back-home" to="/">← Back to Home</Link>
      <ProgressIndicator step={step} />
      <main><Outlet /></main>
      <footer>
        <span>256-bit encrypted</span>
        <span>Secure payment abstraction</span>
        <span>MFA required</span>
        <span>Privacy-first onboarding</span>
      </footer>
    </div>
  )
}
