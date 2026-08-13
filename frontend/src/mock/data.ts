import type { DecisionQuality, GuidedEvaluation, Market, Opportunity, PerformanceSummary, SecurityStatus, User } from '../types'

export const demoUser: User = { id: 'demo-user', firstName: 'Alex', lastName: 'Morgan', email: 'alex@example.test', accountState: 'guided_evaluation', plan: 'Explorer', authority: 'Observer' }
export const evaluation: GuidedEvaluation = { durationDays: 14, daysRemaining: 12, cardRequired: true, autopilotEnabled: false, coPilotPreview: true }
export const securityStatus: SecurityStatus = { emailVerified: true, mfaEnabled: true, paymentCurrent: true, trustedDevice: true }
export const markets: Market[] = [
  { symbol: 'BTC/USD', name: 'Bitcoin', state: 'Ready', trend: 'Bullish', quality: 92 },
  { symbol: 'EUR/USD', name: 'Euro / US Dollar', state: 'Validation', trend: 'Bullish', quality: 86 },
  { symbol: 'NAS100', name: 'Nasdaq 100', state: 'Watch', trend: 'Neutral', quality: 78 },
  { symbol: 'GBP/USD', name: 'British Pound / US Dollar', state: 'Avoid', trend: 'Mixed', quality: 51 },
]
export const opportunities: Opportunity[] = markets.slice(0, 3).map((market, index) => ({
  id: market.symbol, market, rank: index + 1, badge: index === 0 ? 'AI Top Pick' : `#${index + 1} Ranked`, status: market.state as Opportunity['status'],
  thesis: 'Higher-timeframe structure and session conditions support a disciplined continuation setup.',
  counterEvidence: 'Price is approaching a resistance zone; confirmation is required before entry.',
  plan: { setup: 'Structure pullback', entry: '64,180–64,420', stop: '63,620', target1: '65,480', target2: '66,250', riskReward: '1 : 2.4', confidence: 87 - index * 5, session: 'New York' },
}))
export const performance: PerformanceSummary = { netReturn: '+3.8%', totalR: '+6.4R', profitFactor: 1.72, expectancy: '+0.32R', winRate: '58%', maxDrawdown: '-2.1R' }
export const decisionQuality: DecisionQuality = { overall: 88, setupSelection: 91, entryDiscipline: 85, riskDiscipline: 96, management: 78, patience: 90 }
export const feed = ['London session confirmed directional strength', 'EUR/USD moved into validation', 'BTC/USD pullback completed', 'Risk conditions remain within plan']
