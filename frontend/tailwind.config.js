/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 极光渐变主色板
        aurora: {
          purple: '#a855f7',
          pink: '#ec4899',
          cyan: '#00d4ff',
          blue: '#3b82f6',
          indigo: '#667eea',
          violet: '#764ba2',
        },
        // 主色调 - 科技感渐变
        primary: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
          950: '#2e1065',
        },
        // 深邃暗色背景
        dark: {
          900: '#0a0a0f',  // 主背景
          800: '#12121a',  // 卡片背景
          700: '#1a1a25',  // 次级背景
          600: '#252532',  // 边框/悬浮
          500: '#363646',  // 禁用
        },
        // 玻璃效果
        glass: {
          light: 'rgba(255, 255, 255, 0.7)',
          dark: 'rgba(18, 18, 26, 0.8)',
          border: {
            light: 'rgba(255, 255, 255, 0.3)',
            dark: 'rgba(255, 255, 255, 0.08)',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
        display: ['Cal Sans', 'Inter', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '24px',
        '4xl': '32px',
      },
      boxShadow: {
        // 玻璃阴影
        'glass': '0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.6)',
        'glass-dark': '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
        // 辉光阴影
        'glow': '0 0 40px rgba(168, 85, 247, 0.3)',
        'glow-lg': '0 0 60px rgba(168, 85, 247, 0.4)',
        'glow-cyan': '0 0 40px rgba(0, 212, 255, 0.3)',
        'glow-pink': '0 0 40px rgba(236, 72, 153, 0.3)',
        // 卡片阴影
        'card': '0 4px 20px rgba(0, 0, 0, 0.08)',
        'card-hover': '0 20px 40px rgba(0, 0, 0, 0.15)',
        // 柔和阴影
        'soft': '0 2px 15px rgba(0, 0, 0, 0.04)',
        'soft-lg': '0 8px 30px rgba(0, 0, 0, 0.08)',
      },
      backdropBlur: {
        'xs': '2px',
      },
      animation: {
        // 渐变流动
        'gradient': 'gradientFlow 15s ease infinite',
        // 淡入上浮
        'fade-in-up': 'fadeInUp 0.6s ease-out forwards',
        // 淡入
        'fade-in': 'fadeIn 0.4s ease-out forwards',
        // 悬浮
        'float': 'float 6s ease-in-out infinite',
        // 脉冲辉光
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        // 滑入
        'slide-in': 'slideIn 0.5s ease-out forwards',
        // 缩放进入
        'scale-in': 'scaleIn 0.3s ease-out forwards',
        // 微弹
        'bounce-subtle': 'bounceSubtle 0.3s ease-out',
        // 闪烁
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        gradientFlow: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(168, 85, 247, 0.3)' },
          '50%': { boxShadow: '0 0 40px rgba(168, 85, 247, 0.6)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        bounceSubtle: {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.02)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'spring': 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
        'bounce': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
      },
      backgroundImage: {
        // 渐变背景
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-aurora': 'linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #f5576c 75%, #4facfe 100%)',
        'gradient-purple': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'gradient-cyan': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        'gradient-pink': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        // 网格背景
        'grid-pattern': "url(\"data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%239C92AC' fill-opacity='0.05' fill-rule='evenodd'%3E%3Cpath d='M0 40L40 0H20L0 20M40 40V20L20 40'/%3E%3C/g%3E%3C/svg%3E\")",
      },
      backgroundSize: {
        '400%': '400% 400%',
      },
    },
  },
  plugins: [
    // 自定义插件：添加 glass 工具类
    function({ addComponents, addUtilities }) {
      addComponents({
        '.glass': {
          background: 'rgba(255, 255, 255, 0.7)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.3)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.6)',
        },
        '.glass-dark': {
          background: 'rgba(18, 18, 26, 0.8)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
        },
        '.gradient-text': {
          background: 'linear-gradient(135deg, #667eea 0%, #f093fb 50%, #f5576c 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        },
        '.btn-gradient': {
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          borderRadius: '9999px',
          padding: '12px 24px',
          fontWeight: '600',
          transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
          boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4)',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: '0 8px 25px rgba(102, 126, 234, 0.5)',
          },
        },
      });

      addUtilities({
        '.text-balance': {
          textWrap: 'balance',
        },
        '.animation-delay-100': {
          animationDelay: '100ms',
        },
        '.animation-delay-200': {
          animationDelay: '200ms',
        },
        '.animation-delay-300': {
          animationDelay: '300ms',
        },
        '.animation-delay-500': {
          animationDelay: '500ms',
        },
        '.animation-delay-700': {
          animationDelay: '700ms',
        },
      });
    },
  ],
}
