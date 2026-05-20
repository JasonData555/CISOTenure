'use client'

import { useState } from 'react'

const SHARE_TEXT = encodeURIComponent(
  "Hitch Partners just published the most rigorous CISO tenure study ever conducted. 8 years of data. 1,200 CISOs. Here's how long they actually last:"
)

export default function ShareBar() {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    if (typeof window !== 'undefined') {
      navigator.clipboard.writeText(window.location.href).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  const linkedInUrl =
    typeof window !== 'undefined'
      ? `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(window.location.href)}&summary=${SHARE_TEXT}`
      : `https://www.linkedin.com/sharing/share-offsite/?summary=${SHARE_TEXT}`

  const mailtoUrl = `mailto:?subject=${encodeURIComponent('CISO Tenure Study - Hitch Partners')}&body=${encodeURIComponent("I thought you'd find this interesting: ")}`

  return (
    <section className="py-14 px-6 border-y border-hitchLightGray bg-gray-50">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-center gap-6">
        <p className="font-sans font-medium text-hitchDarkTeal text-sm tracking-wide shrink-0">
          Share this research
        </p>

        <div className="flex flex-wrap gap-3 flex-1">
          {/* LinkedIn */}
          <a
            href={linkedInUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 border border-hitchLightGray bg-white rounded-full px-4 py-2 text-xs font-sans font-medium text-hitchDarkTeal hover:border-hitchTeal hover:text-hitchTeal transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            Share on LinkedIn
          </a>

          {/* Email */}
          <a
            href={mailtoUrl}
            className="inline-flex items-center gap-2 border border-hitchLightGray bg-white rounded-full px-4 py-2 text-xs font-sans font-medium text-hitchDarkTeal hover:border-hitchTeal hover:text-hitchTeal transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
              <polyline points="22,6 12,13 2,6"/>
            </svg>
            Email
          </a>

          {/* Copy link */}
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-2 border border-hitchLightGray bg-white rounded-full px-4 py-2 text-xs font-sans font-medium text-hitchDarkTeal hover:border-hitchTeal hover:text-hitchTeal transition-colors"
          >
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Copied!
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/>
                  <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>
                </svg>
                Copy link
              </>
            )}
          </button>
        </div>

        {/* Download PDF — right-aligned */}
        <a
          href="/ciso-tenure-study.pdf"
          className="inline-flex items-center gap-2 bg-hitchDarkTeal text-white rounded-full px-5 py-2.5 text-xs font-sans font-medium hover:bg-hitchTeal transition-colors shrink-0"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download PDF
        </a>
      </div>
    </section>
  )
}
