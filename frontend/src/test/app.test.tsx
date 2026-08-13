import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { isStrongPassword } from '../utils/password'
import { DEV_AUTH_EMAIL, DEV_AUTH_MFA, DEV_AUTH_PASSWORD } from '../config/devAuth'

const renderRoute = (route: string) => render(<MemoryRouter initialEntries={[route]}><App /></MemoryRouter>)

describe('StructureIQ frontend', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_ENABLE_DEV_AUTH', 'false')
  })

  it('loads the public landing page with Guided Evaluation terminology', () => {
    renderRoute('/')
    expect(screen.getByRole('img', { name: /structureiq approved master landing page/i })).toHaveAttribute('src', '/assets/landing-page-v1.1.png')
    expect(screen.getAllByRole('link', { name: /14-Day Guided Evaluation/i }).length).toBeGreaterThan(0)
    expect(screen.queryByText(/free trial/i)).not.toBeInTheDocument()
  })

  it('renders the approved landing image with accessible routing hotspots', () => {
    renderRoute('/')
    expect(screen.getByRole('img', { name: /guided evaluation calls to action/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^StructureIQ home$/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /^Log In$/i })).toHaveAttribute('href', '/signin')
    expect(screen.getByRole('link', { name: /^Start 14-Day Guided Evaluation$/i })).toHaveAttribute('href', '/evaluation/create-account')
    expect(screen.getByRole('link', { name: /^Start Your 14-Day Guided Evaluation$/i })).toHaveAttribute('href', '/evaluation/create-account')
    expect(screen.getByRole('link', { name: /^Pricing$/i })).toHaveAttribute('href', '/pricing')
    expect(screen.queryByRole('link', { name: /^View Morning Brief$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^View Full Outlook$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^View All Opportunities$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^View Full Economic Calendar$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /trade with confidence/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/Preparing Your Morning Intelligence/i)).not.toBeInTheDocument()
  })

  it('renders the approved pricing image with paid-plan hotspots', () => {
    renderRoute('/pricing')
    expect(screen.getByRole('img', { name: /structureiq approved pricing page/i })).toHaveAttribute('src', '/assets/pricing-v1.0.png')
    expect(screen.getByRole('link', { name: /^StructureIQ home$/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /^Log In$/i })).toHaveAttribute('href', '/signin')
    expect(screen.getByRole('link', { name: /^Start 14-Day Guided Evaluation$/i })).toHaveAttribute('href', '/evaluation/create-account')
    expect(screen.getByRole('link', { name: /^Start Explorer$/i })).toHaveAttribute('href', '/evaluation/create-account?plan=explorer')
    expect(screen.getByRole('link', { name: /^Start Professional$/i })).toHaveAttribute('href', '/evaluation/create-account?plan=professional')
    expect(screen.getByRole('link', { name: /^Start Elite$/i })).toHaveAttribute('href', '/evaluation/create-account?plan=elite')
    expect(screen.getByRole('link', { name: /^Start 14-Day Guided Evaluation bottom CTA$/i })).toHaveAttribute('href', '/evaluation/create-account')
    expect(screen.queryByRole('heading', { name: /choose your execution authority/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/^Explorer$/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Professional$/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Elite$/)).not.toBeInTheDocument()
  })

  it.each([
    ['/evaluation/create-account', 'Start Your 14-Day Guided Evaluation'],
    ['/evaluation/payment', 'Activate your 14-day evaluation'],
    ['/evaluation/verify', 'Protect your account'],
    ['/evaluation/welcome', 'Welcome to StructureIQ'],
    ['/forgot-password', 'Reset your password'],
    ['/app', 'Command Center'],
    ['/app/markets', 'Market Intelligence'],
    ['/app/trades', 'Trade Intelligence'],
    ['/app/performance', 'Performance Intelligence'],
  ])('renders route %s', (route, heading) => {
    renderRoute(route)
    expect(screen.getByRole('heading', { name: new RegExp(heading, 'i') })).toBeInTheDocument()
  })

  it.each([
    ['/app', 'AI Confidence'],
    ['/app/markets', 'AI Market Brief'],
    ['/app/trades', 'Opportunity Workspace'],
    ['/app/performance', 'AI Performance Brief'],
  ])('renders actual workspace content for %s', (route, uniqueText) => {
    renderRoute(route)
    const appMain = screen.getByTestId('app-main')
    expect(appMain).toBeInTheDocument()
    expect(appMain).not.toHaveAttribute('hidden')
    expect(within(appMain).getByText(uniqueText, { exact: false })).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-scrim')).toBeInTheDocument()
  })

  it('includes Google sign-in and omits Apple sign-in', () => {
    renderRoute('/signin')
    expect(screen.getByRole('img', { name: /structureiq approved sign in page/i })).toHaveAttribute('src', '/assets/sign-in-page-v1.0.png')
    expect(screen.getByRole('link', { name: /^StructureIQ home$/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeInTheDocument()
    expect(screen.queryByText(/apple/i)).not.toBeInTheDocument()
  })

  it('supports image-overlay sign-in controls and routes', async () => {
    const user = userEvent.setup()
    renderRoute('/signin')
    const email = screen.getByLabelText('Email Address')
    const password = screen.getByLabelText('Password')
    await user.type(email, 'alex@example.test')
    await user.type(password, 'Secret123!')
    expect(email).toHaveValue('alex@example.test')
    expect(email).not.toHaveAttribute('placeholder')
    expect(email).toHaveClass('has-value')
    expect(password).toHaveAttribute('type', 'password')
    expect(password).not.toHaveAttribute('placeholder')
    expect(password).toHaveClass('has-value')
    await user.click(screen.getByRole('button', { name: /show password/i }))
    expect(password).toHaveAttribute('type', 'text')
    await user.clear(email)
    await user.clear(password)
    expect(email).not.toHaveClass('has-value')
    expect(password).not.toHaveClass('has-value')
    expect(screen.getByRole('link', { name: /forgot password/i })).toHaveAttribute('href', '/forgot-password')
    expect(screen.getByRole('link', { name: /start your 14-day guided evaluation/i })).toHaveAttribute('href', '/evaluation/create-account')
    await user.click(screen.getByRole('button', { name: /continue with google/i }))
    expect(await screen.findByText(/Production Google authentication is not connected/i)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /welcome back/i })).not.toBeInTheDocument()
  })

  it('shows a checked-state overlay for Remember this device', async () => {
    const user = userEvent.setup()
    renderRoute('/signin')
    const remember = screen.getByLabelText(/remember this device/i)
    expect(remember).not.toBeChecked()
    expect(document.querySelector('.signin-remember-checkmark')).not.toBeInTheDocument()

    await user.click(remember)
    expect(remember).toBeChecked()
    expect(document.querySelector('.signin-remember-checkmark')).toBeInTheDocument()
    expect(screen.queryByText(/^Remember this device$/)).not.toBeInTheDocument()

    await user.click(remember)
    expect(remember).not.toBeChecked()
    expect(document.querySelector('.signin-remember-checkmark')).not.toBeInTheDocument()

    remember.focus()
    await user.keyboard('[Space]')
    expect(remember).toBeChecked()
    expect(document.querySelector('.signin-remember-checkmark')).toBeInTheDocument()
  })

  it('activates Sign In footer placeholder links without navigation', async () => {
    const user = userEvent.setup()
    renderRoute('/signin')
    const pushState = vi.spyOn(window.history, 'pushState')
    const replaceState = vi.spyOn(window.history, 'replaceState')
    for (const label of ['Privacy Policy', 'Terms of Service', 'Security']) {
      const control = screen.getByRole('button', { name: label })
      expect(control).toBeInTheDocument()
      await user.click(control)
      expect(screen.getByRole('img', { name: /structureiq approved sign in page/i })).toBeInTheDocument()
    }
    expect(pushState).not.toHaveBeenCalled()
    expect(replaceState).not.toHaveBeenCalled()
    expect(screen.queryByText(/^Privacy Policy$/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Terms of Service$/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Security$/)).not.toBeInTheDocument()
    pushState.mockRestore()
    replaceState.mockRestore()
  })

  it('does not authenticate arbitrary credentials when dev auth is disabled', async () => {
    const user = userEvent.setup()
    renderRoute('/signin')
    await user.type(screen.getByLabelText('Email Address'), 'bogus@example.test')
    await user.type(screen.getByLabelText('Password'), 'anything')
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/Production authentication APIs are not connected/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/6-digit authenticator code/i)).not.toBeInTheDocument()
  })

  it('accepts only the documented development auth flow when enabled', async () => {
    vi.stubEnv('VITE_ENABLE_DEV_AUTH', 'true')
    const user = userEvent.setup()
    renderRoute('/signin')
    await user.type(screen.getByLabelText('Email Address'), 'bogus@example.test')
    await user.type(screen.getByLabelText('Password'), 'anything')
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/Invalid development credentials/i)).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Email Address'))
    await user.clear(screen.getByLabelText('Password'))
    await user.type(screen.getByLabelText('Email Address'), DEV_AUTH_EMAIL)
    await user.type(screen.getByLabelText('Password'), DEV_AUTH_PASSWORD)
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByLabelText(/6-digit authenticator code/i)).toBeInTheDocument()

    await user.type(screen.getByLabelText(/6-digit authenticator code/i), DEV_AUTH_MFA)
    await user.click(screen.getByRole('button', { name: /verify and continue/i }))
    expect(await screen.findByRole('heading', { name: /command center/i })).toBeInTheDocument()
  })

  it('keeps development review routes directly renderable when dev auth is enabled', () => {
    vi.stubEnv('VITE_ENABLE_DEV_AUTH', 'true')
    for (const [route, text] of [
      ['/', 'StructureIQ approved master landing page'],
      ['/pricing', 'StructureIQ approved pricing page'],
      ['/signin', 'StructureIQ approved sign in page'],
      ['/evaluation/create-account', 'Start Your 14-Day'],
      ['/evaluation/payment', 'Activate your 14-day evaluation'],
      ['/evaluation/verify', 'Protect your account'],
      ['/evaluation/welcome', 'Welcome to StructureIQ'],
      ['/app', 'AI Confidence'],
      ['/app/markets', 'AI Market Brief'],
      ['/app/trades', 'Opportunity Workspace'],
      ['/app/performance', 'AI Performance Brief'],
    ]) {
      const { unmount } = renderRoute(route)
      if (route === '/' || route === '/signin' || route === '/pricing') {
        expect(screen.getByRole('img', { name: new RegExp(String(text), 'i') })).toBeInTheDocument()
      } else {
        expect(screen.getByText(new RegExp(String(text), 'i'))).toBeInTheDocument()
      }
      unmount()
    }
  })

  it('uses the approved authenticated sidebar hierarchy', () => {
    renderRoute('/app')
    const nav = screen.getByRole('navigation', { name: /primary navigation/i })
    expect(within(nav).getByText('Command Center')).toBeInTheDocument()
    expect(within(nav).getByText('Market Intelligence')).toBeInTheDocument()
    expect(within(nav).getByText('Trade Intelligence')).toBeInTheDocument()
    expect(within(nav).getByText('Performance Intelligence')).toBeInTheDocument()
    expect(screen.getByText('Workspace Tools')).toBeInTheDocument()
    expect(screen.getByText('Account & System')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Dashboard$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Markets$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Trades$/i })).not.toBeInTheDocument()
  })

  it.each(['/app', '/app/markets', '/app/trades', '/app/performance'])('routes authenticated logo home to Command Center for %s', (route) => {
    renderRoute(route)
    expect(screen.getByRole('link', { name: /^StructureIQ home$/i })).toHaveAttribute('href', '/app')
  })

  it('renders all four Guided Evaluation steps', () => {
    for (const route of ['/evaluation/create-account', '/evaluation/payment', '/evaluation/verify', '/evaluation/welcome']) {
      const { unmount } = renderRoute(route)
      expect(screen.getByLabelText(/Step \d of 4/i)).toBeInTheDocument()
      unmount()
    }
  })

  it('enforces approved password requirements', () => {
    expect(isStrongPassword('weak')).toBe(false)
    expect(isStrongPassword('Strong#123')).toBe(true)
  })

  it('supports wizard navigation after valid signup', async () => {
    const user = userEvent.setup()
    renderRoute('/evaluation/create-account')
    await user.type(screen.getByLabelText('First Name'), 'Alex')
    await user.type(screen.getByLabelText('Last Name'), 'Morgan')
    await user.type(screen.getByLabelText('Email Address'), 'alex@example.test')
    await user.type(screen.getByLabelText('Password'), 'Strong#123')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: /continue.*secure payment/i }))
    expect(await screen.findByRole('heading', { name: /activate your 14-day evaluation/i })).toBeInTheDocument()
  })

  it('supports Trade Intelligence AI Top Pick and user override state', async () => {
    const user = userEvent.setup()
    renderRoute('/app/trades')
    expect(screen.getAllByText(/AI Top Pick/i).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: /EUR\/USD/i }))
    expect(screen.getByRole('heading', { name: /EUR\/USD.*Structure pullback/i })).toBeInTheDocument()
  })

  it('keeps Performance Intelligence Edge Score conceptual', () => {
    renderRoute('/app/performance')
    expect(screen.getByText('CONCEPT / FUTURE')).toBeInTheDocument()
    expect(screen.getByText(/Not validated as production capability/i)).toBeInTheDocument()
  })
})
