import { Link } from 'react-router-dom'

export const Brand = ({ compact = false, to = '/' }: { compact?: boolean; to?: string }) => (
  <Link to={to} className="brand" aria-label="StructureIQ home">
    <span className="brand__mark" aria-hidden="true">S</span>
    {!compact && (
      <span className="brand__text">
        STRUCTURE<span>IQ</span>
        <small>AI Trading Operating System</small>
      </span>
    )}
  </Link>
)
