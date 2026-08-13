import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Badge, Button, Card, Checkbox, Divider, Input, PasswordInput } from '../components/primitives'
import { authService, billingService, securityService } from '../services'
import { isStrongPassword, passwordRules } from '../utils/password'
import { DEV_AUTH_MFA, isDevAuthEnabled } from '../config/devAuth'

const workspaceCards = [
  ['Command Center', 'Your daily trading headquarters.'],
  ['Market Intelligence', 'Understand market structure and context.'],
  ['Trade Intelligence', 'Discover high-quality opportunities.'],
  ['Performance Intelligence', 'Review, learn, and improve every day.'],
]

const EvaluationSummary = () => (
  <Card className="evaluation-summary" glow>
    <div className="summary-row">
      <div><Badge tone="purple">14-Day Guided Evaluation</Badge><h2>Explorer Intelligence</h2><p>Professional Co-Pilot Preview Included</p></div>
      <div className="price"><strong>$0</strong><span>Today</span><small>Card Required<br />No Charge Until Evaluation Ends</small></div>
    </div>
  </Card>
)

const WizardIntro = () => (
  <aside className="wizard-intro">
    <h1>Start Your 14-Day <span>Guided Evaluation</span></h1>
    <p>Create your account to experience StructureIQ risk-free for 14 days. No commitment. Cancel anytime before your evaluation ends.</p>
    <div className="workspace-cards">{workspaceCards.map(([title, copy]) => <Card key={title}><i /> <strong>{title}</strong><p>{copy}</p></Card>)}</div>
    <Card className="next-panel">
      <h2>What Happens Next?</h2>
      {['Create your account', 'Secure your evaluation', 'Verify & secure your account', 'Begin your Guided Evaluation'].map((item, index) => <p key={item}><b>{index + 1}</b><strong>{item}</strong><span>{['Tell us a few details to get started.', 'Add a payment method. You won’t be charged today.', 'Verify your email and enable MFA.', 'Complete onboarding and start exploring StructureIQ.'][index]}</span></p>)}
    </Card>
    <Card className="trust-card"><h2>Safe. Secure. Trusted.</h2><ul className="check-list"><li>Payment method required to activate</li><li>You will not be charged today</li><li>Cancel anytime before Day 14</li><li>Mandatory email verification</li><li>Mandatory MFA for all accounts</li></ul></Card>
  </aside>
)

export const CreateAccountPage = () => {
  const nav = useNavigate()
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', password: '', acceptedTerms: false })
  const [error, setError] = useState('')
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!isStrongPassword(form.password) || !form.acceptedTerms) {
      setError('Complete the password and agreement requirements.')
      return
    }
    await authService.createAccount(form)
    nav('/evaluation/payment')
  }

  return (
    <div className="wizard-grid">
      <WizardIntro />
      <section className="wizard-panel">
        <EvaluationSummary />
        <p className="auth-switch">Already have an account? <Link to="/signin">Sign In</Link></p>
        <Button type="button" variant="secondary" className="google-button">G&nbsp;&nbsp; Continue with Google</Button>
        <Divider />
        <form onSubmit={submit} className="form-stack">
          <div className="field-row"><Input label="First Name" required value={form.firstName} onChange={(event) => setForm({ ...form, firstName: event.target.value })} /><Input label="Last Name" required value={form.lastName} onChange={(event) => setForm({ ...form, lastName: event.target.value })} /></div>
          <Input label="Email Address" type="email" required value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
          <PasswordInput value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
          <div className="strength"><i style={{ width: `${passwordRules.filter((rule) => rule.test(form.password)).length * 20}%` }} /><span>{isStrongPassword(form.password) ? 'Strong' : 'Build a strong password'}</span></div>
          <ul className="password-rules compact">{passwordRules.map((rule) => <li className={rule.test(form.password) ? 'pass' : ''} key={rule.label}>✓ {rule.label}</li>)}</ul>
          <Checkbox checked={form.acceptedTerms} onChange={(event) => setForm({ ...form, acceptedTerms: event.target.checked })} label={<>I agree to the <a href="#terms">Terms of Service</a> and <a href="#privacy">Privacy Policy</a>.</>} />
          {error && <Alert tone="critical">{error}</Alert>}
          <Button type="submit">Continue → Secure Payment ▣</Button>
          <small>Your card is required to activate your Guided Evaluation. You will not be charged today.</small>
        </form>
      </section>
    </div>
  )
}

export const PaymentPage = () => {
  const nav = useNavigate()
  const [ack, setAck] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!ack) return
    if (!isDevAuthEnabled()) {
      setError('Payment activation requires production billing APIs. Enable VITE_ENABLE_DEV_AUTH=true only for local visual QA.')
      return
    }
    setBusy(true)
    await billingService.tokenizePayment()
    await billingService.activateEvaluation()
    nav('/evaluation/verify')
  }

  return (
    <div className="wizard-grid">
      <WizardIntro />
      <section className="wizard-panel payment-panel">
        <EvaluationSummary />
        <span className="eyebrow">Secure payment</span>
        <h1>Activate your 14-day evaluation</h1>
        <Alert>Payment provider sandbox UI. Raw card details are not stored by StructureIQ.</Alert>
        <form onSubmit={submit} className="form-stack">
          <Input label="Card Information" inputMode="numeric" placeholder="4242 4242 4242 4242" required />
          <div className="field-row"><Input label="Expiration" placeholder="MM / YY" required /><Input label="CVC" inputMode="numeric" placeholder="123" required /></div>
          <Input label="Name on Card" required />
          <Input label="Billing ZIP / Postal Code" required />
          <Checkbox checked={ack} onChange={(event) => setAck(event.target.checked)} label="I understand I pay $0 today and billing begins after the evaluation unless I cancel." />
          {error && <Alert tone="critical">{error}</Alert>}
          <Button disabled={!ack || busy} type="submit">{busy ? 'Activating…' : 'Activate My 14-Day Guided Evaluation'}</Button>
        </form>
        <Card><strong>What Happens Next</strong><p>We validate your payment method, then guide you through email verification and MFA setup.</p></Card>
      </section>
    </div>
  )
}

export const VerifyPage = () => {
  const nav = useNavigate()
  const [verified, setVerified] = useState(false)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [remember, setRemember] = useState(true)
  const verify = async () => {
    const result = await securityService.verifyMfa(code)
    if (result.ok) {
      setError('')
      nav('/evaluation/welcome')
      return
    }
    setError(result.reason)
  }

  return (
    <div className="wizard-grid">
      <WizardIntro />
      <section className="wizard-panel verify-panel">
        <span className="eyebrow">Verify & secure</span>
        <h1>Protect your account</h1>
        <div className="two-col">
          <Card glow><Badge tone={verified ? 'green' : 'amber'}>{verified ? 'Email verified' : 'Email sent'}</Badge><h2>Email Verification</h2><p>We sent a secure verification link to your account email.</p><Button variant="secondary" onClick={() => setVerified(true)}>{verified ? 'Verified' : 'Simulate verification'}</Button><button className="text-button" type="button">Resend verification email</button></Card>
          <Card><Badge tone="purple">Recommended</Badge><h2>Authenticator App MFA</h2><p>Scan the QR placeholder, enter the six-digit code, and store recovery codes securely.</p></Card>
        </div>
        <div className="mfa-enroll"><div className="qr-placeholder" aria-label="Authenticator QR code placeholder"><span>QR</span></div><ol><li>Open your authenticator app.</li><li>Scan this enrollment placeholder.</li><li>Enter the generated 6-digit code.</li></ol></div>
        <Input label="Six-Digit Code" inputMode="numeric" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))} />
        <Checkbox checked={remember} onChange={(event) => setRemember(event.target.checked)} label="Remember this device for up to 30 days" />
        <Alert tone="warning">Recovery codes will be generated after enrollment. Store them somewhere secure. {isDevAuthEnabled() ? `Use development MFA ${DEV_AUTH_MFA} for local visual QA.` : 'Production MFA APIs are not connected.'}</Alert>
        {error && <Alert tone="critical">{error}</Alert>}
        <Button disabled={!verified || code.length !== 6} onClick={verify}>Continue to Welcome</Button>
      </section>
    </div>
  )
}

export const WelcomePage = () => (
  <section className="welcome-panel">
    <div className="welcome-orbit"><span>SIQ</span></div>
    <Badge tone="green">14-Day Guided Evaluation active</Badge>
    <h1>Welcome to StructureIQ, Alex.</h1>
    <p>Your AI Partner is ready to help you understand markets, make disciplined decisions, and improve from every outcome.</p>
    <div className="welcome-journey">{['Meet your AI Partner', 'Explore Market Intelligence', 'Review Trade Intelligence', 'Build better habits'].map((item, index) => <div key={item}><span>0{index + 1}</span><strong>{item}</strong></div>)}</div>
    <Card glow><strong>Your mission</strong><p>Use the next 14 days to learn how StructureIQ explains markets, prioritizes attention, and supports disciplined decisions before any trade is considered.</p></Card>
    <Card><strong>Your access</strong><p>Command Center · Market Intelligence · Trade Intelligence · Performance Intelligence · Explorer manual execution · Professional Co-Pilot preview · No Autopilot</p></Card>
    <Link to="/onboarding"><Button>Begin My StructureIQ Journey</Button></Link>
    <small>This welcome appears only after first activation. Returning users go directly to Command Center.</small>
  </section>
)
