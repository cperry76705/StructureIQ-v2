import { Navigate, Route, Routes } from 'react-router-dom'
import { PublicLayout } from './layouts/PublicLayout'
import { AuthLayout } from './layouts/AuthLayout'
import { WizardLayout } from './layouts/WizardLayout'
import { AppLayout } from './layouts/AppLayout'
import { LandingPage, PricingPage } from './pages/PublicPages'
import { CreateAccountPage, PaymentPage, VerifyPage, WelcomePage } from './pages/WizardPages'
import { ForgotPasswordPage, ResetConfirmationPage, ResetPasswordPage, SignInPage } from './pages/AuthPages'
import { CommandCenterPage, MarketIntelligencePage, PerformanceIntelligencePage, TradeIntelligencePage } from './pages/WorkspacePages'

export const App = () => <Routes>
  <Route index element={<LandingPage/>}/>
  <Route path="pricing" element={<PricingPage/>}/>
  <Route path="evaluation" element={<WizardLayout/>}><Route index element={<Navigate to="create-account" replace/>}/><Route path="create-account" element={<CreateAccountPage/>}/><Route path="payment" element={<PaymentPage/>}/><Route path="verify" element={<VerifyPage/>}/><Route path="welcome" element={<WelcomePage/>}/></Route>
  <Route path="signin" element={<SignInPage/>}/>
  <Route element={<AuthLayout/>}><Route path="forgot-password" element={<ForgotPasswordPage/>}/><Route path="reset-password" element={<ResetPasswordPage/>}/><Route path="reset-confirmation" element={<ResetConfirmationPage/>}/></Route>
  <Route path="app" element={<AppLayout/>}><Route index element={<CommandCenterPage/>}/><Route path="markets" element={<MarketIntelligencePage/>}/><Route path="trades" element={<TradeIntelligencePage/>}/><Route path="performance" element={<PerformanceIntelligencePage/>}/></Route>
  <Route path="onboarding" element={<AuthLayout/>}><Route index element={<div className="auth-card"><h1>Onboarding coming next</h1><p>Your progress will be saved. Curated mission-based onboarding is reserved for the next phase.</p></div>}/></Route>
  <Route path="*" element={<Navigate to="/" replace/>}/>
</Routes>
