import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './data/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        hitchDarkTeal:  '#0D2426',
        hitchTeal:      '#235857',
        hitchMedTeal:   '#3B8A7F',
        hitchLightGray: '#D3D9D4',
        hitchBlueGray:  '#6D8B8C',
      },
      fontFamily: {
        serif: ['var(--font-serif)', 'Georgia', 'serif'],
        sans:  ['var(--font-sans)', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

export default config
