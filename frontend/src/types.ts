export type AccountState = 'visitor' | 'pending_registration' | 'pending_verification' | 'guided_evaluation' | 'active_explorer' | 'active_professional' | 'active_elite' | 'grace_period' | 'suspended' | 'canceled' | 'locked'
export type Plan = 'Explorer' | 'Professional' | 'Elite'
export type Authority = 'Observer' | 'Advisor' | 'Co-Pilot' | 'Autopilot'
export interface User { id: string; firstName: string; lastName: string; email: string; accountState: AccountState; plan: Plan; authority: Authority }
export interface GuidedEvaluation { durationDays: 14; daysRemaining: number; cardRequired: true; autopilotEnabled: false; coPilotPreview: true }
export interface Market { symbol: string; name: string; state: string; trend: string; quality: number }
export interface TradePlan { setup: string; entry: string; stop: string; target1: string; target2: string; riskReward: string; confidence: number; session: string }
export interface Opportunity { id: string; market: Market; rank: number; badge: string; status: 'Ready' | 'Validation' | 'Watch' | 'Avoid'; thesis: string; counterEvidence: string; plan: TradePlan }
export interface PerformanceSummary { netReturn: string; totalR: string; profitFactor: number; expectancy: string; winRate: string; maxDrawdown: string }
export interface DecisionQuality { overall: number; setupSelection: number; entryDiscipline: number; riskDiscipline: number; management: number; patience: number }
export interface SecurityStatus { emailVerified: boolean; mfaEnabled: boolean; paymentCurrent: boolean; trustedDevice: boolean }
export interface SignupPayload { firstName: string; lastName: string; email: string; password: string; acceptedTerms: boolean }
