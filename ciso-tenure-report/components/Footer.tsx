export default function Footer() {
  return (
    <footer className="bg-hitchDarkTeal text-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div>
            <p className="font-serif text-white text-lg mb-1">Hitch Partners</p>
            <p className="font-sans font-light text-white/60 text-sm">
              Executive Security Leadership Search
            </p>
          </div>

          <div className="flex flex-col items-start md:items-end gap-1">
            <p className="font-sans text-white/60 text-xs">
              Source: Hitch Partners CISO Tenure Study, 2025
            </p>
            <p className="font-sans text-white/60 text-xs">
              Data: 1,549 episodes · 776 profiles · 2017–2025
            </p>
            <a
              href="#methodology"
              className="font-sans text-white/60 text-xs hover:text-white underline underline-offset-2 transition-colors"
            >
              Full methodology →
            </a>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-white/10">
          <p className="font-sans font-light text-white/40 text-xs leading-relaxed max-w-3xl">
            This research is provided for informational purposes only. Findings represent
            historical patterns in the dataset and should not be construed as predictions
            for any individual CISO tenure. All statistical methods and limitations are
            described in the Methodology section above.
          </p>
        </div>
      </div>
    </footer>
  )
}
