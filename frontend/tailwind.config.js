/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        carbon: {
          primary: '#16A34A',
          forest: '#166534',
          darkgreen: '#14532D',
          dark: '#0B0F0C',
          bg: '#FFFFFF',
          secondaryBg: '#F8FAFC',
          text: '#111827',
          mutedText: '#64748B',
          border: '#E2E8F0',
          success: '#16A34A',
          warning: '#D97706',
          error: '#DC2626',
          lightGreen: '#ECFDF5',
          lightGreenBorder: '#A7F3D0',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
