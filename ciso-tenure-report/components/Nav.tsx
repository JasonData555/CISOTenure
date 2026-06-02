'use client'

import { useState } from 'react'

const NAV_LINKS = [
  { label: '01 Survival', href: '#survival' },
  { label: '02 Eras',     href: '#eras' },
  { label: '03 Hazard',   href: '#hazard' },
  { label: '04 Cohort',   href: '#cohort' },
  { label: '05 Size',     href: '#size' },
  { label: '06 Industry', href: '#industry' },
  { label: '07 Sample',   href: '#sample' },
  { label: 'Methodology', href: '#methodology' },
]

export default function Nav() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <nav className="sticky top-0 z-50 bg-white border-b border-hitchLightGray">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <a
          href="#"
          className="font-serif text-hitchDarkTeal text-sm tracking-[0.15em] uppercase select-none"
        >
          Hitch Partners
        </a>

        {/* Desktop anchor links */}
        <div className="hidden md:flex items-center gap-6">
          {NAV_LINKS.map(link => (
            <a
              key={link.href}
              href={link.href}
              className="text-xs font-sans font-medium tracking-wide text-hitchBlueGray hover:text-hitchDarkTeal transition-colors"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* CTA */}
        <div className="flex items-center gap-3">
          <a
            href="mailto:contact@hitchpartners.com"
            className="hidden md:inline-flex items-center gap-1 bg-hitchDarkTeal text-white text-xs font-sans font-medium px-4 py-2 rounded-full hover:bg-hitchTeal transition-colors"
          >
            Contact Hitch →
          </a>
          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 text-hitchDarkTeal"
            onClick={() => setMenuOpen(o => !o)}
            aria-label="Toggle menu"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              {menuOpen ? (
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              ) : (
                <path
                  fillRule="evenodd"
                  d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
                  clipRule="evenodd"
                />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden bg-white border-t border-hitchLightGray px-6 py-4 flex flex-col gap-4">
          {NAV_LINKS.map(link => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className="text-sm font-sans text-hitchDarkTeal"
            >
              {link.label}
            </a>
          ))}
          <a
            href="mailto:contact@hitchpartners.com"
            className="inline-flex items-center gap-1 bg-hitchDarkTeal text-white text-xs font-sans font-medium px-4 py-2 rounded-full w-fit"
          >
            Contact Hitch →
          </a>
        </div>
      )}
    </nav>
  )
}
