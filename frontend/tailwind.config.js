/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#05070D', 900: '#070A12', 850: '#0A0F1A', 800: '#0D1320',
          750: '#111827', 700: '#161F31', 600: '#1E2A3F', 500: '#2A3853',
        },
        cyan: { epoch: '#22D3EE' },
        violet: { epoch: '#8B5CF6' },
        verdict: {
          verified: '#34D399', partial: '#FBBF24', outdated: '#F59E0B',
          contradicted: '#F43F5E', unverified: '#94A3B8', conflicting: '#A78BFA',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Geist', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: { '2xs': ['0.6875rem', { lineHeight: '1rem' }] },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 20px 40px -24px rgba(0,0,0,0.8)',
        glow: '0 0 0 1px rgba(34,211,238,0.25), 0 0 32px -8px rgba(34,211,238,0.35)',
      },
      keyframes: {
        shimmer: { '0%': { backgroundPosition: '-500px 0' }, '100%': { backgroundPosition: '500px 0' } },
        pulseSoft: { '0%,100%': { opacity: '0.35' }, '50%': { opacity: '0.8' } },
      },
      animation: { shimmer: 'shimmer 1.8s linear infinite', pulseSoft: 'pulseSoft 2.4s ease-in-out infinite' },
    },
  },
  plugins: [],
}
