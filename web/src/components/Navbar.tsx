import { NavLink } from 'react-router-dom'
import './Navbar.css'

const LINKS = [
  { to: '/', label: 'Feed' },
  { to: '/favoritos', label: 'Favoritos' },
  { to: '/cupons', label: 'Cupons' },
  { to: '/alertas', label: 'Alertas' },
  { to: '/admin', label: 'Admin' },
]

export function Navbar() {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <span className="navbar-brand">
          <span className="mono">&gt;_</span> PromoWatcher
        </span>
        <nav className="navbar-links">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) => `navbar-link${isActive ? ' active' : ''}`}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
