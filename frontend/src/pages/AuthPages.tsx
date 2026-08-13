import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Alert, Button, Input, PasswordInput } from '../components/primitives'
import { authService, securityService } from '../services'
import { isStrongPassword, passwordRules } from '../utils/password'
import { DEV_AUTH_EMAIL, DEV_AUTH_MFA, DEV_AUTH_PASSWORD, isDevAuthEnabled } from '../config/devAuth'

const SIGN_IN_IMAGE_SRC = '/assets/sign-in-page-v1.0.png'

export const SignInPage = () => {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberDevice, setRememberDevice] = useState(false)
  const [mfa, setMfa] = useState(false)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const result = await authService.signIn(email, password)
    if (result.ok && result.requiresMfa) {
      setError('')
      setMfa(true)
      return
    }
    setError(result.reason)
  }

  const verify = async () => {
    const result = await securityService.verifyMfa(code)
    if (result.ok) {
      setError('')
      nav('/app')
      return
    }
    setError(result.reason)
  }

  return (
    <main className="signin-image-page">
      <div className="signin-image-frame" aria-label="StructureIQ approved sign in page">
        <img
          alt="StructureIQ approved sign in page with Google sign in, email and password fields, security panel, and guided evaluation link."
          className="signin-approved-image"
          src={SIGN_IN_IMAGE_SRC}
        />
        {!mfa ? (
          <form aria-label="Sign in" className="signin-overlay-form" onSubmit={submit}>
            {isDevAuthEnabled() && <p className="signin-overlay-message signin-overlay-message--dev">Dev auth: {DEV_AUTH_EMAIL} / {DEV_AUTH_PASSWORD}</p>}
            <Link aria-label="StructureIQ home" className="signin-logo-hotspot" to="/" />
            <button aria-label="Continue with Google" className="signin-google-hotspot" onClick={() => setError('Production Google authentication is not connected in this environment.')} type="button" />

            <label className="sr-only" htmlFor="signin-email">Email Address</label>
            <input
              autoComplete="email"
              className={`signin-field signin-email-field${email ? ' has-value' : ''}`}
              id="signin-email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />

            <label className="sr-only" htmlFor="signin-password">Password</label>
            <input
              autoComplete="current-password"
              className={`signin-field signin-password-field${password ? ' has-value' : ''}`}
              id="signin-password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type={showPassword ? 'text' : 'password'}
              value={password}
            />

            <button
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="signin-eye-hotspot"
              onClick={() => setShowPassword((value) => !value)}
              type="button"
            />

            <label className="signin-remember-hotspot">
              <input
                aria-label="Remember this device"
                checked={rememberDevice}
                onChange={(event) => setRememberDevice(event.target.checked)}
                type="checkbox"
              />
              {rememberDevice && <span aria-hidden="true" className="signin-remember-checkmark">✓</span>}
            </label>

            <Link aria-label="Forgot password?" className="signin-forgot-hotspot" to="/forgot-password" />
            {error && <p className="signin-overlay-message signin-overlay-message--error">{error}</p>}
            <button aria-label="Sign In" className="signin-submit-hotspot" type="submit" />
            <Link aria-label="Start Your 14-Day Guided Evaluation" className="signin-evaluation-hotspot" to="/evaluation/create-account" />
            <button aria-label="Privacy Policy" className="signin-privacy-hotspot" type="button" />
            <button aria-label="Terms of Service" className="signin-terms-hotspot" type="button" />
            <button aria-label="Security" className="signin-security-hotspot" type="button" />
          </form>
        ) : (
          <section aria-label="Multi-factor authentication" className="signin-mfa-overlay">
            <p>{isDevAuthEnabled() ? `Development MFA required. Use ${DEV_AUTH_MFA} for local visual QA only.` : 'Multi-factor verification requires production authentication APIs.'}</p>
            <label htmlFor="signin-mfa-code">6-digit authenticator code</label>
            <input id="signin-mfa-code" inputMode="numeric" maxLength={6} onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))} value={code} />
            {error && <p className="signin-overlay-message signin-overlay-message--error">{error}</p>}
            <button onClick={verify} type="button">Verify and continue</button>
          </section>
        )}
      </div>
    </main>
  )
}

export const ForgotPasswordPage = () => {
  const [sent, setSent] = useState(false)
  return (
    <section className="auth-card">
      <span className="eyebrow">Account recovery</span>
      <h1>Reset your password</h1>
      <p>Enter your verified email. If an account exists, we’ll send a secure reset link.</p>
      {sent ? <Alert tone="success">Check your email for the secure reset link.</Alert> : <><Input label="Email" type="email" /><Button onClick={() => setSent(true)}>Send reset link</Button></>}
      <Link to="/signin">← Return to Sign In</Link>
    </section>
  )
}

export const ResetPasswordPage = () => {
  const nav = useNavigate()
  const [value, setValue] = useState('')
  return (
    <section className="auth-card">
      <span className="eyebrow">Secure reset</span>
      <h1>Create a new password</h1>
      <PasswordInput label="New password" value={value} onChange={(event) => setValue(event.target.value)} />
      <ul className="password-rules">{passwordRules.map((rule) => <li className={rule.test(value) ? 'pass' : ''} key={rule.label}>{rule.test(value) ? '✓' : '○'} {rule.label}</li>)}</ul>
      <Button disabled={!isStrongPassword(value)} onClick={() => nav('/reset-confirmation')}>Reset password</Button>
    </section>
  )
}

export const ResetConfirmationPage = () => (
  <section className="auth-card auth-card--center">
    <span className="success-icon">✓</span>
    <h1>Password updated</h1>
    <p>Your password has been reset. Sign in again with your new credentials.</p>
    <Link to="/signin"><Button>Return to Sign In</Button></Link>
  </section>
)
