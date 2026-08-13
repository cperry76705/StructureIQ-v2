import { decisionQuality, demoUser, evaluation, markets, opportunities, performance, securityStatus } from '../mock/data'
import type { SignupPayload } from '../types'
import { validateDevCredentials, validateDevMfa } from '../config/devAuth'

const delay = <T,>(value: T) => new Promise<T>((resolve) => window.setTimeout(() => resolve(value), 120))
export const authService = {
  currentUser: () => delay(demoUser),
  createAccount: (payload: SignupPayload) => delay({ ok: Boolean(payload.email && payload.acceptedTerms), accountState: 'pending_registration' as const }),
  signIn: (email: string, password: string) => delay(validateDevCredentials(email, password)),
  requestPasswordReset: (email: string) => delay({ ok: Boolean(email) }),
}
export const billingService = { activateEvaluation: () => delay({ ok: true, evaluation }), tokenizePayment: () => delay({ token: 'mock-provider-token' }) }
export const marketService = { list: () => delay(markets) }
export const tradeService = { opportunities: () => delay(opportunities), topPick: () => delay(opportunities[0]) }
export const performanceService = { summary: () => delay({ performance, decisionQuality }) }
export const securityService = { status: () => delay(securityStatus), verifyMfa: (code: string) => delay(validateDevMfa(code)) }
