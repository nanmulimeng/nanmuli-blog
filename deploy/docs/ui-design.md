# Nanmuli Blog - UI设计重构方案 v2.0

> **设计主题**: Aurora Glass（极光玻璃）
> **设计风格**: 前卫创新 / 玻璃拟态 / 极光渐变 / 深邃暗色

---

## 一、设计理念

### 1.1 核心概念

```
┌─────────────────────────────────────────────────────────────┐
│                    AURORA GLASS 设计系统                     │
├─────────────────────────────────────────────────────────────┤
│  🌌 极光流动 - 动态渐变背景，营造科技感与艺术感              │
│  💎 玻璃质感 - Glassmorphism 深度层次，半透明磨砂效果        │
│  ⚡ 灵动动效 - 微交互动画，提升用户参与感                    │
│  🌙 双主题适配 - Light/Dark 无缝切换，照顾不同场景           │
│  🎯 内容优先 - 克制装饰，突出技术文章内容                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 设计关键词

- **前卫**: 打破传统博客布局，采用不对称、层叠、悬浮设计
- **创新**: 引入 3D 透视、视差滚动、粒子背景等现代效果
- **整洁**: 大量留白、清晰的视觉层级、克制的色彩使用
- **美观**: 精心打磨的圆角、阴影、渐变细节

---

## 二、色彩系统

### 2.1 主色调（极光渐变）

```css
/* Primary Gradient - 极光紫蓝 */
--gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #f5576c 75%, #4facfe 100%);

/* Accent Colors */
--accent-cyan: #00d4ff;      /* 霓虹青 */
--accent-purple: #a855f7;    /* 极光紫 */
--accent-pink: #ec4899;      /* 霓虹粉 */
--accent-blue: #3b82f6;      /* 科技蓝 */
```

### 2.2 Light 主题

```css
/* 背景层级 */
--bg-primary: #fafafa;           /* 主背景 - 极浅灰 */
--bg-secondary: #ffffff;         /* 卡片背景 - 纯白 */
--bg-tertiary: #f4f4f5;          /* 次级背景 */
--bg-glass: rgba(255,255,255,0.7); /* 玻璃背景 */

/* 文字层级 */
--text-primary: #18181b;         /* 主文字 - 近黑 */
--text-secondary: #52525b;       /* 次级文字 - 深灰 */
--text-tertiary: #a1a1aa;        /* 辅助文字 - 中灰 */
--text-muted: #d4d4d8;           /* 禁用文字 - 浅灰 */

/* 边框与分割 */
--border-primary: rgba(0,0,0,0.08);
--border-glass: rgba(255,255,255,0.5);
--divider: rgba(0,0,0,0.06);
```

### 2.3 Dark 主题

```css
/* 背景层级 - 深邃暗色 */
--bg-primary: #0a0a0f;           /* 主背景 - 深邃黑 */
--bg-secondary: #12121a;         /* 卡片背景 - 午夜蓝 */
--bg-tertiary: #1a1a25;          /* 次级背景 */
--bg-glass: rgba(18,18,26,0.8);  /* 玻璃背景 */

/* 文字层级 */
--text-primary: #fafafa;         /* 主文字 - 近白 */
--text-secondary: #a1a1aa;       /* 次级文字 - 浅灰 */
--text-tertiary: #71717a;        /* 辅助文字 - 中灰 */
--text-muted: #52525b;           /* 禁用文字 - 深灰 */

/* 边框与分割 */
--border-primary: rgba(255,255,255,0.08);
--border-glass: rgba(255,255,255,0.1);
--divider: rgba(255,255,255,0.06);
```

---

## 三、视觉元素

### 3.1 玻璃拟态 (Glassmorphism)

```css
/* 基础玻璃效果 */
.glass {
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.3);
  box-shadow: 
    0 8px 32px rgba(0,0,0,0.1),
    inset 0 1px 0 rgba(255,255,255,0.6);
}

/* Dark 模式玻璃 */
.glass-dark {
  background: rgba(18,18,26,0.8);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 
    0 8px 32px rgba(0,0,0,0.4),
    inset 0 1px 0 rgba(255,255,255,0.05);
}
```

### 3.2 圆角系统

```css
--radius-sm: 8px;     /* 小按钮、标签 */
--radius-md: 12px;    /* 输入框、小卡片 */
--radius-lg: 16px;    /* 卡片、面板 */
--radius-xl: 24px;    /* 大卡片、模态框 */
--radius-2xl: 32px;   /* Hero 区域 */
--radius-full: 9999px;/* 胶囊按钮、头像 */
```

### 3.3 阴影系统

```css
/* Light 主题 */
--shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
--shadow-md: 0 4px 12px rgba(0,0,0,0.08);
--shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
--shadow-xl: 0 16px 48px rgba(0,0,0,0.16);
--shadow-glow: 0 0 40px rgba(168,85,247,0.3); /* 紫色辉光 */

/* Dark 主题 */
--shadow-glow-dark: 0 0 60px rgba(168,85,247,0.4);
```

---

## 四、排版系统

### 4.1 字体

```css
/* 中文主字体 - 现代黑体 */
--font-sans: 'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;

/* 英文/代码字体 */
--font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;

/* 标题装饰字体（可选） */
--font-display: 'Cal Sans', 'Inter', sans-serif;
```

### 4.2 字号层级

```css
/* Hero 标题 */
--text-hero: 4rem;      /* 64px - Hero 大标题 */
--text-display: 3rem;   /* 48px - 页面标题 */

/* 标题层级 */
--text-h1: 2.5rem;      /* 40px */
--text-h2: 2rem;        /* 32px */
--text-h3: 1.5rem;      /* 24px */
--text-h4: 1.25rem;     /* 20px */

/* 正文层级 */
--text-lg: 1.125rem;    /* 18px - 大正文 */
--text-base: 1rem;      /* 16px - 标准正文 */
--text-sm: 0.875rem;    /* 14px - 小字 */
--text-xs: 0.75rem;     /* 12px - 标签 */
```

### 4.3 字重

```css
--font-normal: 400;
--font-medium: 500;     /* 强调 */
--font-semibold: 600;   /* 小标题 */
--font-bold: 700;       /* 大标题 */
--font-black: 800;      /* Hero */
```

---

## 五、动效系统

### 5.1 缓动函数

```css
--ease-default: cubic-bezier(0.4, 0, 0.2, 1);
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
--ease-smooth: cubic-bezier(0.16, 1, 0.3, 1);      /* 推荐 */
--ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
```

### 5.2 时长规范

```css
--duration-instant: 100ms;   /* 按钮点击 */
--duration-fast: 200ms;      /* 悬停效果 */
--duration-normal: 300ms;    /* 页面过渡 */
--duration-slow: 500ms;      /* 复杂动画 */
--duration-slower: 800ms;    /* 入场动画 */
```

### 5.3 预设动画

```css
/* 淡入上浮 - 卡片入场 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 渐变流动 - Hero 背景 */
@keyframes gradientFlow {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

/* 悬浮效果 */
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

/* 脉冲辉光 */
@keyframes pulseGlow {
  0%, 100% { box-shadow: 0 0 20px rgba(168,85,247,0.3); }
  50% { box-shadow: 0 0 40px rgba(168,85,247,0.6); }
}

/* 滑入 */
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
```

---

## 六、页面设计规范

### 6.1 全局布局

```
┌─────────────────────────────────────────────────────────────┐
│  导航栏 (Fixed, Glassmorphism, 高度 72px)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                       Main Content                          │
│              (max-width: 1280px, 居中)                      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                      Footer                                 │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 首页 (Home) 结构

```
┌─────────────────────────────────────────────────────────────┐
│  Hero Section                                               │
│  - 全宽渐变背景 (animated gradient)                         │
│  - 左侧: 大标题 + 副标题 + CTA 按钮                         │
│  - 右侧: 3D 悬浮卡片/代码装饰                               │
│  - 高度: 90vh                                               │
├─────────────────────────────────────────────────────────────┤
│  Stats Bar (Glass Card, 悬浮重叠)                           │
│  - 文章数 / 代码行数 / 运行天数 等统计                      │
├─────────────────────────────────────────────────────────────┤
│  Featured Articles                                          │
│  - 标题区: 左侧标题 + 右侧 "查看全部"                       │
│  - 卡片网格: 3列 (桌面) / 2列 (平板) / 1列 (手机)           │
│  - 卡片样式: Glass + Hover 上浮 + 渐变边框                  │
├─────────────────────────────────────────────────────────────┤
│  Categories (横向滚动/标签云)                               │
│  - 分类标签: Pill shape + 图标 + 数量                       │
│  - 悬停: 背景渐变 + 缩放                                    │
├─────────────────────────────────────────────────────────────┤
│  Recent Daily Logs (时间线样式)                             │
│  - 垂直时间线设计                                           │
│  - 节点: 渐变圆点                                           │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 文章列表页

```
┌─────────────────────────────────────────────────────────────┐
│  页面标题区                                                  │
│  - 背景: 渐变标题栏                                         │
│  - 搜索框: Glass 样式，居中                                 │
│  - 分类筛选: 横向滚动 Pill 标签                             │
├─────────────────────────────────────────────────────────────┤
│  文章网格 (Masonry Layout 可选)                             │
│  - 卡片: 封面图 + 标题 + 摘要 + 元信息                      │
│  - 悬停: 图片缩放 + 卡片上浮 + 阴影加深                     │
├─────────────────────────────────────────────────────────────┤
│  分页器                                                      │
│  - 简约设计，Previous / Next + 页码                         │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 文章详情页

```
┌─────────────────────────────────────────────────────────────┐
│  文章头图 (全宽, max-height: 400px)                         │
├─────────────────────────────────────────────────────────────┤
│  文章标题区                                                  │
│  - 分类标签: 渐变 Pill                                      │
│  - 标题: 大号粗体                                           │
│  - 元信息: 作者/日期/阅读时间/阅读量                        │
├─────────────────────────────────────────────────────────────┤
│  文章内容区                                                  │
│  - max-width: 720px (最佳阅读宽度)                          │
│  - 代码块: Dark theme + 语法高亮 + 复制按钮                 │
│  - 引用块: 左侧渐变边框                                     │
│  - 图片: 圆角 + 阴影 + 点击放大                             │
├─────────────────────────────────────────────────────────────┤
│  文章底部                                                    │
│  - 标签: 渐变 Pill                                          │
│  - 分享按钮: Glass Icon Buttons                             │
│  - 上一篇/下一篇: 卡片导航                                  │
├─────────────────────────────────────────────────────────────┤
│  评论区 (预留)                                               │
└─────────────────────────────────────────────────────────────┘
```

### 6.5 导航组件

```
Desktop Navigation:
┌─────────────────────────────────────────────────────────────┐
│  [Logo]    Home  Articles  Logs  Tags  Projects  About    [Search] [Theme Toggle]
│            ────  (Active: 渐变下划线或背景)                 │
└─────────────────────────────────────────────────────────────┘

Mobile Navigation:
┌─────────────────────────────────────────────────────────────┐
│  [Logo]                                          [Menu ☰]   │
├─────────────────────────────────────────────────────────────┤
│  Full-screen Overlay Menu (Glass)                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ✕                                                     │  │
│  │                                                       │  │
│  │  Home                                                 │  │
│  │  Articles                                             │  │
│  │  ...                                                  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 七、组件设计规范

### 7.1 按钮样式

```css
/* Primary Button - 渐变背景 */
.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 9999px;
  padding: 12px 24px;
  font-weight: 600;
  transition: all 0.3s var(--ease-smooth);
  box-shadow: 0 4px 15px rgba(102,126,234,0.4);
}
.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(102,126,234,0.5);
}

/* Secondary Button - Glass */
.btn-secondary {
  background: rgba(255,255,255,0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 9999px;
  padding: 12px 24px;
  transition: all 0.3s var(--ease-smooth);
}

/* Ghost Button */
.btn-ghost {
  background: transparent;
  border-radius: 12px;
  padding: 8px 16px;
  transition: all 0.2s;
}
.btn-ghost:hover {
  background: rgba(0,0,0,0.05);
}
```

### 7.2 卡片样式

```css
/* Article Card */
.card-article {
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 24px;
  overflow: hidden;
  transition: all 0.4s var(--ease-smooth);
}
.card-article:hover {
  transform: translateY(-8px) scale(1.02);
  box-shadow: 0 20px 40px rgba(0,0,0,0.15);
}

/* Feature Card - 渐变边框 */
.card-feature {
  position: relative;
  background: white;
  border-radius: 24px;
  padding: 2px; /* 边框宽度 */
}
.card-feature::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 24px;
  background: linear-gradient(135deg, #667eea, #f093fb, #f5576c);
  z-index: -1;
}
```

### 7.3 输入框样式

```css
.input-glass {
  background: rgba(255,255,255,0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 16px;
  padding: 14px 20px;
  transition: all 0.3s;
}
.input-glass:focus {
  background: rgba(255,255,255,0.15);
  border-color: rgba(168,85,247,0.5);
  box-shadow: 0 0 0 4px rgba(168,85,247,0.1);
  outline: none;
}
```

---

## 八、响应式断点

```css
/* Mobile First */
--breakpoint-sm: 640px;   /* 大屏手机 */
--breakpoint-md: 768px;   /* 平板 */
--breakpoint-lg: 1024px;  /* 小桌面 */
--breakpoint-xl: 1280px;  /* 标准桌面 */
--breakpoint-2xl: 1536px; /* 大桌面 */
```

### 布局适配

| 断点 | 导航 | 文章网格 | Hero |
|------|------|----------|------|
| < 640px | 汉堡菜单 | 1列 | 堆叠布局 |
| 640-768px | 汉堡菜单 | 1列 | 堆叠布局 |
| 768-1024px | 完整导航 | 2列 | 左右布局 |
| > 1024px | 完整导航 | 3列 | 左右布局 + 装饰 |

---

## 九、特殊效果实现

### 9.1 动态渐变背景 (Hero)

```css
.hero-gradient {
  background: linear-gradient(
    -45deg,
    #667eea,
    #764ba2,
    #f093fb,
    #f5576c,
    #4facfe,
    #00f2fe
  );
  background-size: 400% 400%;
  animation: gradientFlow 15s ease infinite;
}
```

### 9.2 网格渐变背景 (装饰)

```css
.grid-gradient {
  background-image: 
    radial-gradient(circle at 20% 50%, rgba(120,119,198,0.3) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(255,119,198,0.3) 0%, transparent 50%),
    radial-gradient(circle at 40% 20%, rgba(120,219,255,0.2) 0%, transparent 40%);
}
```

### 9.3 噪声纹理叠加

```css
.noise-overlay {
  position: relative;
}
.noise-overlay::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  opacity: 0.03;
  pointer-events: none;
}
```

---

## 十、文件结构规划

```
frontend/src/
├── styles/
│   ├── index.scss           # 入口，导入所有样式
│   ├── design-system.scss   # 设计系统变量
│   ├── animations.scss      # 动画定义
│   ├── markdown.scss        # Markdown 内容样式
│   └── dark-mode.scss       # 暗色主题
├── components/
│   ├── ui/                  # 基础UI组件
│   │   ├── GlassCard.vue
│   │   ├── GradientButton.vue
│   │   ├── PillTag.vue
│   │   └── AnimatedText.vue
│   └── ...
├── layouts/
│   ├── DefaultLayout.vue    # 重构后布局
│   └── AdminLayout.vue
├── views/
│   ├── home/Index.vue       # 重构后首页
│   └── ...
└── composables/
    └── useTheme.ts          # 主题切换
```

---

## 十一、实现优先级

1. **P0 - 核心框架**
   - [x] 设计文档
   - [ ] Tailwind 配置更新（颜色/阴影/动画）
   - [ ] 全局样式系统（Light/Dark 变量）
   - [ ] 主题切换功能

2. **P1 - 基础组件**
   - [ ] GlassCard 组件
   - [ ] GradientButton 组件
   - [ ] PillTag 组件
   - [ ] 重构导航栏

3. **P2 - 核心页面**
   - [ ] Hero 首页
   - [ ] 文章列表页
   - [ ] 文章详情页

4. **P3 - 优化**
   - [ ] 动效优化
   - [ ] 性能优化
   - [ ] 无障碍支持

---

> **设计版本**: v2.0 Aurora Glass
> **创建日期**: 2026-04-05
> **设计师**: Claude Code
