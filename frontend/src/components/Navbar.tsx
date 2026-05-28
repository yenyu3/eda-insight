import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Upload' },
  { to: '/history', label: 'History' },
  { to: '/compare', label: 'Compare' },
]

export default function Navbar() {
  const { pathname } = useLocation()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header className={`header${scrolled ? ' scrolled' : ''}`}>
      <div className="container header-inner">
        <Link to="/" className="logo-link">
          <span className="logo-img logo-mark">EI</span>
          <h1 className="sitename logo-name">
            <span>EDA Insight</span>
            <span>Workflow</span>
          </h1>
        </Link>

        <div className="navmenu">
          <nav aria-label="Primary navigation">
            <ul>
              {NAV_ITEMS.map(({ to, label }) => (
                <li key={to}>
                  <Link
                    to={to}
                    className={pathname === to ? 'active' : ''}
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
    </header>
  )
}
