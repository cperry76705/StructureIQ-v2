import { Link } from 'react-router-dom'

const LANDING_IMAGE_SRC = '/assets/landing-page-v1.1.png'
const PRICING_IMAGE_SRC = '/assets/pricing-v1.0.png'

const hotspots = [
  { label: 'StructureIQ home', to: '/', left: 2.8, top: 1.2, width: 12.6, height: 4.2 },
  { label: 'Platform', href: '#platform', left: 24.3, top: 2.2, width: 4.7, height: 3.1 },
  { label: 'How It Works', href: '#how', left: 30.1, top: 2.2, width: 7.2, height: 3.1 },
  { label: 'Features', href: '#features', left: 38.2, top: 2.2, width: 5.4, height: 3.1 },
  { label: 'Pricing', to: '/pricing', left: 44.4, top: 2.2, width: 4.5, height: 3.1 },
  { label: 'Resources', href: '#resources', left: 49.7, top: 2.2, width: 6.8, height: 3.1 },
  { label: 'Company', href: '#company', left: 57.4, top: 2.2, width: 6.2, height: 3.1 },
  { label: 'Log In', to: '/signin', left: 71.3, top: 1.35, width: 7.0, height: 3.9 },
  { label: 'Start 14-Day Guided Evaluation', to: '/evaluation/create-account', left: 79.4, top: 1.35, width: 17.4, height: 3.9 },
  { label: 'Start Your 14-Day Guided Evaluation', to: '/evaluation/create-account', left: 3.95, top: 44.0, width: 21.3, height: 5.2 },
  { label: 'Watch a Live Morning Briefing', href: '#morning-briefing', left: 26.45, top: 44.0, width: 12.35, height: 5.2 },
]

type Hotspot = typeof hotspots[number]

const hotspotStyle = ({ left, top, width, height }: Hotspot) => ({
  left: `${left}%`,
  top: `${top}%`,
  width: `${width}%`,
  height: `${height}%`,
})

const LandingHotspot = (hotspot: Hotspot) => {
  const className = 'landing-image-hotspot'
  const style = hotspotStyle(hotspot)

  if ('to' in hotspot && hotspot.to) {
    return <Link key={hotspot.label} aria-label={hotspot.label} className={className} style={style} to={hotspot.to} />
  }

  return <a key={hotspot.label} aria-label={hotspot.label} className={className} href={hotspot.href} style={style} />
}

const pricingHotspots = [
  { label: 'StructureIQ home', to: '/', left: 1.6, top: .8, width: 17.6, height: 3.2 },
  { label: 'Platform', href: '/#platform', left: 22.3, top: 1.2, width: 5.2, height: 2.0 },
  { label: 'How It Works', href: '/#how', left: 29.5, top: 1.2, width: 7.3, height: 2.0 },
  { label: 'Features', href: '/#features', left: 38.6, top: 1.2, width: 5.6, height: 2.0 },
  { label: 'Pricing', to: '/pricing', left: 46.1, top: 1.2, width: 4.8, height: 2.0 },
  { label: 'Resources', href: '/#resources', left: 52.4, top: 1.2, width: 7.3, height: 2.0 },
  { label: 'Company', href: '/#company', left: 61.5, top: 1.2, width: 7.0, height: 2.0 },
  { label: 'Log In', to: '/signin', left: 72.4, top: .95, width: 6.8, height: 2.75 },
  { label: 'Start 14-Day Guided Evaluation', to: '/evaluation/create-account', left: 80.55, top: .95, width: 17.9, height: 2.75 },
  { label: 'Start Explorer', to: '/evaluation/create-account?plan=explorer', left: 6.4, top: 39.6, width: 24.3, height: 2.55 },
  { label: 'Start Professional', to: '/evaluation/create-account?plan=professional', left: 36.3, top: 39.6, width: 26.2, height: 2.55 },
  { label: 'Start Elite', to: '/evaluation/create-account?plan=elite', left: 68.0, top: 39.6, width: 24.9, height: 2.55 },
  { label: 'Explorer plan recommendation', to: '/evaluation/create-account?plan=explorer', left: 2.9, top: 68.0, width: 30.0, height: 11.8 },
  { label: 'Professional plan recommendation', to: '/evaluation/create-account?plan=professional', left: 34.2, top: 68.0, width: 30.7, height: 11.8 },
  { label: 'Elite plan recommendation', to: '/evaluation/create-account?plan=elite', left: 66.1, top: 68.0, width: 30.8, height: 11.8 },
  { label: 'Start 14-Day Guided Evaluation bottom CTA', to: '/evaluation/create-account', left: 62.2, top: 94.0, width: 30.2, height: 2.8 },
]

type PricingHotspot = typeof pricingHotspots[number]

const pricingHotspotStyle = ({ left, top, width, height }: PricingHotspot) => ({
  left: `${left}%`,
  top: `${top}%`,
  width: `${width}%`,
  height: `${height}%`,
})

const PricingHotspot = (hotspot: PricingHotspot) => {
  const className = 'pricing-image-hotspot'
  const style = pricingHotspotStyle(hotspot)

  if ('to' in hotspot && hotspot.to) {
    return <Link key={hotspot.label} aria-label={hotspot.label} className={className} style={style} to={hotspot.to} />
  }

  return <a key={hotspot.label} aria-label={hotspot.label} className={className} href={hotspot.href} style={style} />
}

export const LandingPage = () => (
  <main className="landing-image-page">
    <div className="landing-image-frame" aria-label="StructureIQ approved landing page">
      <img
        alt="StructureIQ approved master landing page showing AI market intelligence and guided evaluation calls to action."
        className="landing-approved-image"
        src={LANDING_IMAGE_SRC}
      />
      <nav aria-label="Approved landing page interactive hotspots">
        {hotspots.map((hotspot) => <LandingHotspot key={hotspot.label} {...hotspot} />)}
      </nav>
    </div>
  </main>
)

export const PricingPage = () => (
  <main className="pricing-image-page">
    <div className="pricing-image-frame" aria-label="StructureIQ approved pricing page">
      <img
        alt="StructureIQ approved pricing page showing Explorer, Professional, and Elite launch pricing plans."
        className="pricing-approved-image"
        src={PRICING_IMAGE_SRC}
      />
      <nav aria-label="Approved pricing page interactive hotspots">
        {pricingHotspots.map((hotspot) => <PricingHotspot key={hotspot.label} {...hotspot} />)}
      </nav>
    </div>
  </main>
)
