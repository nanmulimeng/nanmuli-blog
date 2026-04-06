/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 主题色 - 通过 CSS 变量动态设置
        primary: {
          DEFAULT: 'var(--theme-primary)',
          light: 'var(--theme-primary-light)',
          dark: 'var(--theme-primary-dark)',
        },
        // 背景色
        surface: {
          primary: 'var(--theme-bg-primary)',
          secondary: 'var(--theme-bg-secondary)',
          tertiary: 'var(--theme-bg-tertiary)',
          card: 'var(--theme-bg-card)',
        },
        // 文字色
        content: {
          primary: 'var(--theme-text-primary)',
          secondary: 'var(--theme-text-secondary)',
          tertiary: 'var(--theme-text-tertiary)',
          inverse: 'var(--theme-text-inverse)',
        },
        // 边框
        border: {
          DEFAULT: 'var(--theme-border)',
          light: 'var(--theme-border-light)',
        },
        // 状态色
        success: 'var(--theme-success)',
        warning: 'var(--theme-warning)',
        error: 'var(--theme-error)',
        info: 'var(--theme-info)',
        // 扩展颜色
        purple: {
          DEFAULT: '#A855F7',
          light: '#C084FC',
        },
        danger: 'var(--theme-error)',
        // 暗色层级
        dark: {
          900: '#0a0a0f',
          800: '#12121a',
          700: '#1a1a25',
          600: '#252532',
        },
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '24px',
      },
      boxShadow: {
        // 主题阴影
        'sm': 'var(--theme-shadow-sm)',
        'DEFAULT': 'var(--theme-shadow)',
        'md': 'var(--theme-shadow-md)',
        'lg': 'var(--theme-shadow-lg)',
        'glow': 'var(--theme-shadow-glow)',
        // 玻璃效果
        'glass': '0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
      },
      backdropBlur: {
        'xs': '2px',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out forwards',
        'fade-in-up': 'fadeInUp 0.4s ease-out forwards',
        'float': 'float 6s ease-in-out infinite',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 20px var(--theme-primary)' },
          '50%': { boxShadow: '0 0 40px var(--theme-primary)' },
        },
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      backgroundImage: {
        'gradient-theme': 'var(--theme-gradient)',
        'gradient-text': 'var(--theme-gradient-text)',
        'grid-pattern': "url(\"data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%239C92AC' fill-opacity='0.03' fill-rule='evenodd'%3E%3Cpath d='M0 40L40 0H20L0 20M40 40V20L20 40'/%3E%3C/g%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [
    function({ addComponents, addUtilities }) {
      addComponents({
        // 玻璃卡片
        '.glass-card': {
          background: 'var(--theme-glass)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid var(--theme-glass-border)',
          borderRadius: '16px',
          boxShadow: 'var(--theme-shadow)',
          transition: 'all 0.3s ease',
        },
        // 玻璃态按钮
        '.btn-glass': {
          background: 'var(--theme-glass)',
          backdropFilter: 'blur(10px)',
          border: '1px solid var(--theme-border)',
          borderRadius: '12px',
          padding: '10px 24px',
          fontWeight: '500',
          transition: 'all 0.2s ease',
          '&:hover': {
            background: 'var(--theme-bg-secondary)',
            borderColor: 'var(--theme-primary)',
          },
        },
        // 渐变按钮
        '.btn-gradient': {
          background: 'var(--theme-gradient)',
          color: 'white',
          borderRadius: '8px',
          padding: '10px 24px',
          fontWeight: '500',
          transition: 'all 0.2s ease',
          boxShadow: 'var(--theme-shadow-glow)',
          '&:hover': {
            transform: 'translateY(-1px)',
            boxShadow: 'var(--theme-shadow-md)',
          },
        },
        // 渐变文字
        '.gradient-text': {
          background: 'var(--theme-gradient-text)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        },
        // 次要按钮
        '.btn-secondary': {
          background: 'var(--theme-bg-tertiary)',
          color: 'var(--theme-text-primary)',
          borderRadius: '8px',
          padding: '10px 24px',
          fontWeight: '500',
          border: '1px solid var(--theme-border)',
          transition: 'all 0.2s ease',
          '&:hover': {
            background: 'var(--theme-bg-secondary)',
            borderColor: 'var(--theme-primary)',
          },
        },
        // 标签
        '.pill': {
          display: 'inline-flex',
          alignItems: 'center',
          padding: '6px 16px',
          borderRadius: '9999px',
          fontSize: '0.875rem',
          fontWeight: '500',
          transition: 'all 0.2s ease',
          cursor: 'pointer',
        },
        '.pill-gradient': {
          background: 'var(--theme-gradient)',
          color: 'white',
          boxShadow: 'var(--theme-shadow-glow)',
        },
        '.pill-glass': {
          background: 'var(--theme-glass)',
          color: 'var(--theme-text-secondary)',
          border: '1px solid var(--theme-border)',
          '&:hover': {
            background: 'var(--theme-bg-secondary)',
            borderColor: 'var(--theme-primary)',
            color: 'var(--theme-primary)',
          },
        },
        '.pill-primary': {
          background: 'var(--theme-primary)',
          color: 'white',
        },
        '.pill-secondary': {
          background: 'var(--theme-bg-tertiary)',
          color: 'var(--theme-text-secondary)',
          border: '1px solid var(--theme-border)',
        },
        // 卡片阴影
        '.shadow-card': {
          boxShadow: 'var(--theme-shadow)',
        },
        '.shadow-card-hover': {
          boxShadow: 'var(--theme-shadow-md)',
        },
      })

      // 添加工具类
      addUtilities({
        '.text-balance': {
          textWrap: 'balance',
        },
      })
    },
  ],
}
