import type { CSSProperties } from 'react'
import { useState } from 'react'
import { MiniChart } from '../components/Chart'
import { Badge, Button, Card, MetricCard, SectionHeader, StatusPill, Tabs } from '../components/primitives'
import { decisionQuality, feed, markets, opportunities, performance } from '../mock/data'

const WorkspaceHeader = ({ title, description, ai = false }: { title: string; description: string; ai?: boolean }) => (
  <header className="workspace-header">
    <div><h1>{title} {ai && <Badge tone="blue">AI</Badge>}</h1><p>{description}</p></div>
  </header>
)

const ScoreBar = ({ label, value }: { label: string; value: number }) => <div className="score-bar"><span>{label}</span><div><i style={{ width: `${value}%` }} /></div><b>{value}</b></div>
const Timeline = ({ items = feed }: { items?: string[] }) => <div className="timeline">{items.map((item, index) => <div key={item}><span className={index === 0 ? 'current' : ''} /><div><small>08:{20 + index * 7} AM</small><p>{item}</p></div></div>)}</div>
const ConfidenceGauge = ({ value, label = 'Bullish' }: { value: number; label?: string }) => <div className="gauge"><i style={{ '--value': `${value}%` } as CSSProperties} /><strong>{value}</strong><span>{label}</span></div>

export const CommandCenterPage = () => (
  <>
    <WorkspaceHeader title="Command Center" description="Real-Time Intelligence. Smarter Decisions." />
    <div className="dashboard-grid command-dashboard">
      <Card className="metric-tile"><SectionHeader title="AI Confidence" /><ConfidenceGauge value={84} label="Bullish" /><small>Overall Market Bias</small></Card>
      <Card className="metric-tile"><MetricCard label="Opportunities" value="3" detail="High Quality Setups" /><a>View Opportunities →</a></Card>
      <Card className="metric-tile"><MetricCard label="Portfolio Risk" value="0.62%" detail="Risk Limit 2.00%" tone="green" /><ScoreBar label="Current risk" value={62} /></Card>
      <Card className="metric-tile"><MetricCard label="Daily P&L" value="+$1,248.75" detail="+0.84%" tone="green" /></Card>
      <Card className="metric-tile"><MetricCard label="Win Rate" value="68%" detail="34 Wins / 16 Losses" /></Card>
      <Card className="metric-tile"><MetricCard label="Trades Today" value="2" detail="Open Positions" tone="purple" /></Card>
      <Card className="metric-tile ai-insight"><span className="eyebrow">AI Insight</span><p>Volatility is expected to increase after 10:00 AM ET due to OPEC and economic releases. Expect potential liquidity expansion across FX and Crypto.</p><a>View Full Insight →</a></Card>

      <Card className="span-6 market-map-card"><SectionHeader title="Market Overview" action={<Tabs tabs={['Overview', 'Indices', 'Forex', 'Crypto']} active="Overview" onChange={() => undefined} />} /><div className="world-map"><span>New York<br /><b>+0.42%</b></span><span>London<br /><b>+0.18%</b></span><span>Tokyo<br /><b>+0.25%</b></span><span>Sydney<br /><b>+0.31%</b></span></div><div className="sentiment-strip"><strong>Cautiously Bullish</strong><i /></div></Card>
      <Card className="span-4"><SectionHeader title="Top Opportunities" action={<a>View All Opportunities →</a>} />{opportunities.map((opportunity) => <div className="opportunity-card" key={opportunity.id}><div><strong>{opportunity.market.symbol}</strong><Badge tone={opportunity.rank === 1 ? 'purple' : 'blue'}>{opportunity.plan.setup}</Badge></div><MiniChart variant={opportunity.rank === 3 ? undefined : 'green'} /><div className="chart-levels"><span>Entry {opportunity.plan.entry}</span><span>Target {opportunity.plan.target1}</span><span>Stop {opportunity.plan.stop}</span></div></div>)}</Card>
      <div className="side-stack">
        <Card><SectionHeader title="Open Positions" />{['BTC/USD +1.72%', 'EUR/USD +0.68%'].map((item) => <div className="position-card" key={item}><strong>{item}</strong><MiniChart variant="green" /><p>Entry Price 66,150 · Stop Loss 65,200</p></div>)}</Card>
        <Card><SectionHeader title="Upcoming Events" />{['10:00 AM OPEC Meeting', '10:30 AM US CPI (MoM)', '02:00 PM FOMC Member Speaks'].map((item) => <p key={item}>{item} <Badge tone={item.includes('CPI') ? 'red' : 'amber'}>{item.includes('CPI') ? 'High Impact' : 'Medium Impact'}</Badge></p>)}</Card>
        <Card><SectionHeader title="Learning & Coaching" /><p>Next Lesson: Managing Trades Like a Professional</p><ScoreBar label="Complete" value={72} /></Card>
      </div>
      <Card className="span-6"><SectionHeader title="Recent Trades" /><div className="trade-table">{['XAU/USD Long +1.89R Target Hit', 'GBP/USD Short +1.24R Target Hit', 'BTC/USD Long -0.86R Stop Hit', 'NAS100 Short +2.15R Target Hit'].map((row) => <span key={row}>{row}</span>)}</div></Card>
      <Card className="span-4"><SectionHeader title="Daily Scorecard" /><div className="ring-score"><span>72%</span></div><ScoreBar label="Discipline" value={82} /><ScoreBar label="Execution" value={68} /><ScoreBar label="Risk Management" value={74} /></Card>
    </div>
  </>
)

export const MarketIntelligencePage = () => (
  <>
    <WorkspaceHeader title="Market Intelligence" description="Understand the market. Find your edge." ai />
    <div className="workspace-grid market-intel-grid">
      <Card className="span-5" glow><SectionHeader eyebrow="AI Market Brief" title="Global risk sentiment remains moderately positive this morning." /><ul className="insight-list"><li>Bitcoin continues respecting higher-timeframe structure.</li><li>EUR/USD remains bullish during London session.</li><li>Three markets currently meet preferred trading conditions.</li><li>Volatility is increasing across major FX pairs ahead of CPI.</li></ul></Card>
      <Card className="span-2"><SectionHeader title="Market Sentiment" /><ConfidenceGauge value={62} label="Bullish" /><MiniChart variant="green" /></Card>
      <Card className="span-4"><SectionHeader title="Market Health Dashboard" /><div className="market-table">{markets.map((market) => <div key={market.symbol}><b>{market.symbol}</b><span>{market.trend}</span><span>{market.quality >= 90 ? 'A' : market.quality >= 80 ? 'B+' : 'C'}</span><StatusPill tone={market.state === 'Ready' ? 'green' : market.state === 'Avoid' ? 'red' : 'amber'}>{market.state === 'Ready' ? 'Excellent' : market.state}</StatusPill></div>)}</div></Card>
      <Card className="span-3 analysis-rail"><SectionHeader title="AI Analysis" /><h2>EUR/USD</h2><Badge tone="green">Bias: Bullish</Badge><p><b>Structure</b><br />EUR/USD continues respecting bullish structure established during London session.</p><p><b>Price Action</b><br />Buyers defended the 1.1210 support zone twice overnight.</p><p><b>Momentum</b><br />Constructive but slowing as price approaches high-impact news.</p><p><b>Key Levels</b><br />Resistance: 1.1270 · 1.1300<br />Support: 1.1210 · 1.1175</p></Card>
      <Card className="span-2"><SectionHeader title="Opportunity Radar" />{markets.map((market, index) => <div className="rank-row" key={market.symbol}><b>{index + 1}</b><span>{market.symbol}</span><strong>{market.quality}</strong></div>)}</Card>
      <Card className="span-7 chart-card"><SectionHeader eyebrow="Chart Analysis" title="EUR/USD · 1H" action={<><Button variant="secondary">Indicators</Button><Button variant="secondary">AI Overlays</Button></>} /><MiniChart variant="green" /><div className="chart-overlays"><span>Resistance Zone</span><span>Support Zone</span><span>London Session</span><span>CPI in 2h 8m</span></div></Card>
      <Card className="span-3"><SectionHeader title="Session Intelligence" /><div className="compact-list"><span>London <b>Strong · Open</b></span><span>New York <b>Building · 1h 8m</b></span><span>Asia <b>Quiet · 7h 8m</b></span></div></Card>
      <Card className="span-3"><SectionHeader title="Market Drivers" /><div className="compact-list"><span>USD <b>↓ Softer</b></span><span>Oil <b>↓ Declining</b></span><span>Crypto <b>↑ Inflows</b></span><span>Rates <b>↑ 10Y rising</b></span></div></Card>
      <Card className="span-3"><SectionHeader title="Economic Calendar" /><div className="compact-list"><span>10:00 AM EUR CPI m/m <b>High</b></span><span>2:30 PM USD PPI m/m <b>Medium</b></span><span>4:00 PM Retail Sales <b>High</b></span></div></Card>
      <Card className="span-3"><SectionHeader title="Volatility Overview" /><div className="compact-list"><span>EUR/USD <b>12.4 ↑</b></span><span>GBP/USD <b>11.8 ↑</b></span><span>USD/JPY <b>9.1 ↓</b></span><span>BTC/USD <b>18.7 ↑</b></span></div></Card>
      <Card className="span-12"><SectionHeader title="AI Observation Timeline" action={<a>View Full Timeline →</a>} /><Timeline items={['Market open analysis completed. Risk sentiment moderately positive.', 'Structure breakout confirmed on BTC above 62,800.', 'EUR/USD retest of 1.1210 support failed. Buyers stepping in.', 'London session volatility increasing as expected.', 'CPI release in 2h 8m. Reducing confidence across major pairs.']} /></Card>
    </div>
  </>
)

export const TradeIntelligencePage = () => {
  const [active, setActive] = useState(opportunities[0])
  const [mode, setMode] = useState('AI Focus')
  return (
    <>
      <WorkspaceHeader title="Trade Intelligence" description="Actionable opportunities. Disciplined execution. Consistent results." />
      <div className="trade-top">
        <Card glow><SectionHeader eyebrow="AI Trade Brief" title="Three opportunities meet StructureIQ's quality threshold today." /><p>BTC/USD remains the highest-quality setup after a pullback. EUR/USD requires a break above 1.0890 to confirm continuation. Gold remains avoided due to weak structure and rising volatility risk.</p></Card>
        <Card><SectionHeader title="Trade Quality Index" /><strong className="hero-score">87</strong><p>Very Strong · ▲ 6 vs yesterday</p><MiniChart variant="green" /></Card>
        <Card><SectionHeader title="Market Environment" /><h2 className="positive">Bullish</h2><p>Risk: On · Moderate Volatility</p><MiniChart variant="green" /></Card>
        <Card><SectionHeader title="Best Session" /><h2>London / NY Overlap</h2><p>High Liquidity · 1h 08m remaining</p><ScoreBar label="Session" value={70} /></Card>
      </div>
      <div className="trade-approved-layout">
        <aside className="trade-left">
          <Card><Tabs tabs={['AI Focus', 'Market Explorer']} active={mode} onChange={setMode} /><SectionHeader title={mode === 'AI Focus' ? 'Top Opportunities' : 'Market Universe'} />{opportunities.map((opportunity) => <button className={`opportunity-item ${active.id === opportunity.id ? 'is-active' : ''}`} key={opportunity.id} onClick={() => setActive(opportunity)}><span><b>{opportunity.market.symbol}</b><small>{opportunity.market.name}</small></span><Badge tone={opportunity.rank === 1 ? 'purple' : 'blue'}>{opportunity.badge}</Badge><i>{opportunity.plan.confidence}%</i></button>)}</Card>
          <Card><SectionHeader title="Opportunity Radar" /><div className="radar"><div className="radar__rings" /></div><div className="compact-list"><span>High Quality <b>3</b></span><span>Moderate <b>6</b></span><span>Low Quality <b>5</b></span><span>Avoid <b>2</b></span></div></Card>
          <Card><SectionHeader title="Market Universe" /><ScoreBar label="Active Opportunities" value={80} /><ScoreBar label="Under Observation" value={62} /><ScoreBar label="Low Quality / Avoid" value={42} /></Card>
        </aside>
        <main className="trade-main">
          <Card glow><SectionHeader eyebrow="Opportunity Workspace" title={`${active.market.symbol} · ${active.plan.setup}`} action={<><Badge tone="purple">{active.badge}</Badge><Badge tone="green">Ready</Badge></>} /><MiniChart variant="green" /><div className="chart-levels"><span>Entry {active.plan.entry}</span><span>Stop {active.plan.stop}</span><span>Target {active.plan.target1}</span></div></Card>
          <div className="two-col"><Card><SectionHeader title="Trade Plan" /><div className="plan-grid">{Object.entries(active.plan).map(([key, value]) => <span key={key}><small>{key.replace(/([A-Z])/g, ' $1')}</small><b>{value}{key === 'confidence' ? '%' : ''}</b></span>)}</div></Card><Card><SectionHeader title="AI Confidence Breakdown" /><ScoreBar label="Structure" value={98} /><ScoreBar label="Momentum" value={91} /><ScoreBar label="Risk" value={85} /><ScoreBar label="Volatility" value={82} /><ScoreBar label="Execution" value={89} /><ConfidenceGauge value={active.plan.confidence} label="Overall Confidence" /></Card></div>
          <div className="two-col"><Card><SectionHeader title="Why This Trade?" /><p>{active.thesis}</p><ul className="check-list"><li>Higher low structure aligns with trend.</li><li>Pullback completed into support zone.</li><li>No high-impact news in the next two hours.</li></ul></Card><Card><SectionHeader title="Why Not This Trade?" /><p>{active.counterEvidence}</p><ul className="risk-list"><li>Resistance zone overhead may cause pause.</li><li>Conservative confirmation is still required.</li></ul></Card></div>
        </main>
        <aside className="trade-right">
          <Card><SectionHeader title="Execution Panel" /><p>How would you like to execute?</p><div className="mode-toggle"><button>Manual</button><button className="active">Approval</button><button disabled>Autopilot · Elite</button></div><Button variant="secondary">Approve Trade</Button><small>Trade will be sent to you for review and approval before execution.</small></Card>
          <Card><SectionHeader title="Trade Lifecycle" /><div className="lifecycle">{['Research', 'Validation', 'Entry', 'Management', 'Exit', 'Review', 'Learning'].map((step, index) => <span className={index < 2 ? 'complete' : index === 2 ? 'current' : ''} key={step}>{step}</span>)}</div><small>Current Stage: Awaiting Entry</small></Card>
          <Card><SectionHeader title="Alternative Scenarios" /><p>↑ Bullish path: continuation toward target.</p><p>↓ Bearish path: structure breaks below support.</p><p>⚠ News scenario: volatility spike; stand aside.</p></Card>
          <Card><SectionHeader title="AI Observation Timeline" /><Timeline items={['Pullback into demand zone completed.', 'Buyers defended support.', 'Entry conditions nearly satisfied.']} /></Card>
          <Card><SectionHeader title="Today’s Lesson" /><p>Why StructureIQ waited for confirmation instead of chasing yesterday’s breakout.</p><Button variant="secondary">Read Full Explanation</Button></Card>
        </aside>
      </div>
      <Card className="span-12 help-band"><div><strong>Not in AI Focus?</strong><p>Browse all supported markets in Market Explorer.</p></div><Button variant="secondary">Open Market Explorer</Button><div><strong>Market not supported?</strong><p>Request exploratory analysis. Results will be exploratory.</p></div><Button variant="secondary">Request Analysis</Button><div><strong>Need help?</strong><p>Learn how Trade Intelligence works.</p></div><Button variant="secondary">View Guide</Button></Card>
    </>
  )
}

export const PerformanceIntelligencePage = () => {
  const [range, setRange] = useState('7D')
  return (
    <>
      <WorkspaceHeader title="Performance Intelligence ✧" description="Understand your performance. Improve your decisions. Grow your edge." />
      <div className="performance-grid">
        <Card className="span-5" glow><SectionHeader eyebrow="AI Performance Brief" title="Your trading improved this week." /><p>Decision Quality increased from 89% to 94%, primarily because you waited for confirmation on four setups you previously would have entered early.</p><a>View Full Analysis →</a></Card>
        <Card className="span-2"><SectionHeader title="Decision Quality" /><strong className="hero-score">{decisionQuality.overall + 6}</strong><p>Excellent · ▲ 3 pts this week</p><MiniChart variant="green" /></Card>
        <Card className="span-4"><SectionHeader title="Performance Summary" /><Tabs tabs={['Today', '7D', '30D', '90D', 'YTD', 'All']} active={range} onChange={setRange} /><div className="metrics-grid">{Object.entries(performance).map(([key, value]) => <MetricCard key={key} label={key.replace(/([A-Z])/g, ' $1')} value={value} />)}</div></Card>
        <Card className="span-3 ai-coach"><SectionHeader title="AI Coach" /><h3>Let winners reach your targets.</h3><p>Your exits reduce average expectancy by ~0.5R. Strong entries deserve stronger management.</p><Button variant="secondary">Start Coaching Session</Button></Card>
        <Card className="span-7"><SectionHeader title="Equity Curve" action={<Badge tone="neutral">Illustrative data</Badge>} /><MiniChart variant="green" /></Card>
        <Card className="span-4"><SectionHeader title="Performance Attribution" /><div className="donut"><span>+4.25R<br />Total</span></div><div className="compact-list"><span>EUR/USD <b>+3.60R</b></span><span>BTC/USD <b>+1.25R</b></span><span>NAS100 <b>+0.85R</b></span><span>GBP/USD <b>-0.65R</b></span></div></Card>
        <Card className="span-3"><SectionHeader title="Performance Milestones" /><ul className="check-list"><li>10 trades within risk plan</li><li>5 consecutive disciplined sessions</li><li>+5R in a week</li></ul><ScoreBar label="Next: rule following" value={60} /></Card>
        <Card className="span-9"><SectionHeader title="Discipline Intelligence" /><div className="discipline-grid">{[['Patience', 96], ['Risk Discipline', 100], ['Rule Adherence', 93], ['Entry Discipline', 88], ['Exit Quality', 76], ['Overtrading Risk', 92]].map(([label, value]) => <div key={label}><ConfidenceGauge value={Number(value)} label={String(label)} /></div>)}</div></Card>
        <Card className="span-3 concept-card"><SectionHeader title="StructureIQ Edge Score" /><Badge tone="neutral">CONCEPT / FUTURE</Badge><strong className="edge-score">72 /100</strong><p>Developing Edge. Measures repeatability and quality of your trading edge over time. Not validated as production capability.</p><Button variant="secondary" disabled>Coming Soon</Button></Card>
        <Card className="span-3"><SectionHeader title="Strengths" /><ul className="check-list"><li>Excellent patience and selective entries.</li><li>Strong adherence to risk management.</li><li>Research completion rate is excellent.</li></ul></Card>
        <Card className="span-3"><SectionHeader title="Needs Improvement" /><ul className="risk-list"><li>Winners closed early.</li><li>Manual overrides reduced expectancy.</li><li>Consider widening profit targets on trends.</li></ul></Card>
        <Card className="span-3"><SectionHeader title="Missed Opportunity Intelligence" /><p><b>Correct Skip:</b> BTC/USD later rallied; no confirmation existed at the time.</p><p><b>Execution Miss:</b> EUR/USD met all rules; no entry recorded.</p></Card>
        <Card className="span-3"><SectionHeader title="Quick Insights" /><div className="compact-list"><span>Best day <b>Tue</b></span><span>Most challenging <b>Wed</b></span><span>Best market <b>EUR/USD</b></span><span>Focus area <b>Exit management</b></span></div></Card>
        <Card className="span-12 help-band"><div><strong>Understand Your Edge</strong><p>Explore attribution to see where your edge is strongest.</p></div><Button variant="secondary">Explore Attribution</Button><div><strong>Review Your Trades</strong><p>Revisit trades to reinforce good decisions.</p></div><Button variant="secondary">Review Trades</Button><div><strong>Improve Consistency</strong><p>Coaching focuses on better habits.</p></div><Button variant="secondary">View Coaching</Button></Card>
      </div>
    </>
  )
}
