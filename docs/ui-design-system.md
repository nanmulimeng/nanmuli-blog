# Nanmuli Blog - UI设计系统

## 1. 设计原则

### 1.1 整体风格
- **风格定位**: 简洁现代、专业克制、注重阅读体验
- **设计理念**: 内容优先，留白充足，视觉层级清晰
- **核心原则**: 少即是多，信息层级不超过3层

### 1.2 配色方案
```
主色调:     primary-600 #0284c7 ( sky blue )
主色浅版:   primary-50  #f0f9ff
主色深版:   primary-700 #0369a1

背景色:     #FFFFFF (纯白) / #FAFAFA (极浅灰)
卡片背景:   #FFFFFF
表面背景:   #F3F4F6

文字主色:   #1F2937 (深灰)
文字次要:   #6B7280 (中灰)
文字辅助:   #9CA3AF (浅灰)

边框:       #E5E7EB
分割线:     #F3F4F6

成功色:     #10B981 (绿)
警告色:     #F59E0B (橙)
错误色:     #EF4444 (红)
```

### 1.3 字体系统
```
字体栈: Inter, system-ui, -apple-system, "Segoe UI", sans-serif
代码字体: "Fira Code", "JetBrains Mono", monospace

字号阶梯:
- 页面标题:  28-32px / font-bold / line-height 1.2
- 区块标题:  20-24px / font-semibold / line-height 1.3
- 卡片标题:  16-18px / font-semibold / line-height 1.4
- 正文:      14-16px / font-normal / line-height 1.7
- 辅助文字:  12-13px / font-normal / line-height 1.5
```

### 1.4 间距系统 (4px基准)
```
xs:  4px
sm:  8px
md:  12px
lg:  16px
xl:  24px
2xl: 32px
3xl: 48px
4xl: 64px

卡片内边距: 16-24px
容器最大宽度: 1280px (max-w-7xl)
容器内边距: 16px (px-4) / 24px (sm:px-6) / 32px (lg:px-8)
```

### 1.5 圆角与阴影
```
圆角:
- 按钮: 8px (rounded-lg)
- 卡片: 12px (rounded-xl)
- 输入框: 8px
- 标签: 9999px (rounded-full)

阴影:
- 卡片默认: shadow-sm (0 1px 2px rgba(0,0,0,0.05))
- 卡片悬停: shadow-lg (0 10px 15px rgba(0,0,0,0.1))
- 导航栏: shadow-sm
```

### 1.6 动效规范
```
悬停过渡:   150ms ease
点击反馈:   100ms scale(0.98)
页面切换:   250ms
列表 stagger: 30ms

缓动函数:   cubic-bezier(0.4, 0, 0.2, 1)
```

---

## 2. 组件设计规范

### 2.1 按钮 Button

#### 主按钮 (Primary)
```vue
<template>
  <button class="
    h-10 px-6 rounded-lg
    bg-primary-600 text-white
    font-medium text-sm
    transition-all duration-150
    hover:bg-primary-700
    active:scale-[0.98]
    disabled:opacity-50 disabled:cursor-not-allowed
  ">
    按钮文字
  </button>
</template>
```

#### 次级按钮 (Secondary)
```vue
<template>
  <button class="
    h-10 px-6 rounded-lg
    border border-gray-300 bg-white text-gray-700
    font-medium text-sm
    transition-all duration-150
    hover:bg-gray-50 hover:border-gray-400
    active:scale-[0.98]
  ">
    按钮文字
  </button>
</template>
```

#### 文字按钮 (Text)
```vue
<template>
  <button class="
    h-10 px-4 rounded-lg
    text-primary-600
    font-medium text-sm
    transition-all duration-150
    hover:bg-primary-50
  ">
    按钮文字
  </button>
</template>
```

### 2.2 卡片 Card

#### 文章卡片 (ArticleCard)
```vue
<template>
  <article class="
    bg-white rounded-xl p-6
    border border-gray-100
    shadow-sm
    transition-all duration-150
    hover:shadow-lg hover:-translate-y-0.5
    cursor-pointer
  ">
    <!-- 标签行 -->
    <div class="flex items-center gap-3 mb-4">
      <span class="
        px-2.5 py-1 rounded-full
        bg-primary-50 text-primary-600
        text-xs font-medium
      ">
        分类名称
      </span>
      <span class="text-sm text-gray-400">2026年4月4日</span>
      <span v-if="isTop" class="text-amber-500 text-xs font-medium">置顶</span>
    </div>
    
    <!-- 标题 -->
    <h3 class="text-lg font-semibold text-gray-900 mb-3 line-clamp-2 group-hover:text-primary-600">
      文章标题
    </h3>
    
    <!-- 摘要 -->
    <p class="text-gray-600 text-sm line-clamp-2 mb-4 leading-relaxed">
      文章摘要内容...
    </p>
    
    <!-- 底部信息 -->
    <div class="flex items-center justify-between text-sm text-gray-400">
      <div class="flex items-center gap-4">
        <span class="flex items-center gap-1">
          <el-icon><View /></el-icon> 阅读 128
        </span>
        <span class="flex items-center gap-1">
          <el-icon><Clock /></el-icon> 5分钟
        </span>
      </div>
      <div class="flex gap-2">
        <span class="px-2 py-0.5 bg-gray-100 rounded text-xs">标签1</span>
        <span class="px-2 py-0.5 bg-gray-100 rounded text-xs">标签2</span>
      </div>
    </div>
  </article>
</template>
```

#### 项目卡片 (ProjectCard)
```vue
<template>
  <div class="
    bg-white rounded-xl overflow-hidden
    border border-gray-100 shadow-sm
    transition-all duration-150
    hover:shadow-lg
  ">
    <!-- 封面图 -->
    <div class="aspect-video bg-gray-100 relative overflow-hidden">
      <img 
        src="cover.jpg" 
        class="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
        alt="项目封面"
      >
    </div>
    
    <!-- 内容 -->
    <div class="p-5">
      <h3 class="text-lg font-semibold text-gray-900 mb-2">项目名称</h3>
      <p class="text-gray-600 text-sm line-clamp-2 mb-4 leading-relaxed">
        项目描述...
      </p>
      
      <!-- 技术栈 -->
      <div class="flex flex-wrap gap-2 mb-4">
        <span class="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600">Vue 3</span>
        <span class="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600">TypeScript</span>
      </div>
      
      <!-- 链接 -->
      <div class="flex gap-3">
        <a class="text-primary-600 text-sm hover:underline flex items-center gap-1">
          <el-icon><Link /></el-icon> 演示
        </a>
        <a class="text-gray-600 text-sm hover:text-gray-900 flex items-center gap-1">
          <el-icon><Promotion /></el-icon> GitHub
        </a>
      </div>
    </div>
  </div>
</template>
```

### 2.3 标签 Tag

```vue
<!-- 默认标签 -->
<span class="
  inline-flex items-center px-3 py-1 rounded-full
  bg-gray-100 text-gray-700
  text-sm font-medium
  transition-colors duration-150
  hover:bg-gray-200
">
  标签名
</span>

<!-- 主色标签 -->
<span class="
  inline-flex items-center px-3 py-1 rounded-full
  bg-primary-50 text-primary-600
  text-sm font-medium
">
  标签名
</span>

<!-- 可点击标签 -->
<button class="
  inline-flex items-center px-4 py-1.5 rounded-full
  bg-white border border-gray-200
  text-sm text-gray-700
  transition-all duration-150
  hover:border-primary-300 hover:text-primary-600
">
  标签名 <span class="ml-1.5 text-gray-400">12</span>
</button>
```

### 2.4 输入框 Input

```vue
<template>
  <div class="relative">
    <input 
      type="text"
      class="
        w-full h-10 px-4 rounded-lg
        border border-gray-300 bg-white
        text-sm text-gray-900
        placeholder:text-gray-400
        transition-colors duration-150
        focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100
      "
      placeholder="请输入内容"
    >
  </div>
</template>
```

### 2.5 搜索框 SearchInput

```vue
<template>
  <div class="relative">
    <el-icon class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
      <Search />
    </el-icon>
    <input 
      type="text"
      class="
        w-full h-11 pl-10 pr-4 rounded-lg
        border border-gray-300 bg-white
        text-sm text-gray-900
        placeholder:text-gray-400
        transition-all duration-150
        focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100
      "
      placeholder="搜索文章..."
    >
  </div>
</template>
```

---

## 3. 页面设计规范

### 3.1 页面布局结构

```
┌─────────────────────────────────────────────────────────────┐
│  Header (固定顶部)                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Logo        导航链接          搜索  主题切换        │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Main Content (flex-1, min-h-screen)                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Footer                                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  版权信息 | 链接 | 社交图标                           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 导航栏 (AppHeader)

```vue
<template>
  <header 
    class="fixed left-0 right-0 top-0 z-50 transition-all duration-300"
    :class="{ 
      'bg-white/95 shadow-sm backdrop-blur-md': isScrolled, 
      'bg-transparent': !isScrolled 
    }"
  >
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="flex h-16 items-center justify-between">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2">
          <img v-if="siteLogo" :src="siteLogo" class="h-8 w-8" alt="logo">
          <span class="text-xl font-bold text-gray-900">{{ siteName }}</span>
        </router-link>
        
        <!-- 桌面导航 -->
        <nav class="hidden md:flex items-center gap-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="isActive(item.path) 
              ? 'text-primary-600 bg-primary-50' 
              : 'text-gray-600 hover:text-primary-600 hover:bg-gray-50'"
          >
            {{ item.label }}
          </router-link>
        </nav>
        
        <!-- 操作区 -->
        <div class="flex items-center gap-2">
          <button class="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors">
            <el-icon :size="20"><Search /></el-icon>
          </button>
          <button class="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors">
            <el-icon :size="20"><Sunny /></el-icon>
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
```

### 3.3 页脚 (AppFooter)

```vue
<template>
  <footer class="bg-white border-t border-gray-200">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex flex-col md:flex-row items-center justify-between gap-4">
        <div class="text-sm text-gray-500">
          © 2026 {{ siteName }}. All rights reserved.
        </div>
        <div class="flex items-center gap-6">
          <a href="#" class="text-gray-400 hover:text-gray-600 transition-colors">
            <el-icon :size="20"><GitHub /></el-icon>
          </a>
          <a href="#" class="text-gray-400 hover:text-gray-600 transition-colors">
            <el-icon :size="20"><Mail /></el-icon>
          </a>
        </div>
      </div>
    </div>
  </footer>
</template>
```

---

## 4. 页面详细设计

### 4.1 首页 (Home)

```
┌─────────────────────────────────────────────────────────────┐
│  Hero Section (py-20, gradient background)                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │              记录技术成长                           │   │
│  │       分享学习心得，探索技术边界                     │   │
│  │                                                     │   │
│  │         [浏览文章]  [技术日志]                       │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Stats Section (optional)                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   128 文章   |   32 项目   |   50 日志   |   365天   │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Latest Articles (py-16)                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   最新文章                              查看全部 →  │   │
│  │                                                     │   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │   │ Article  │  │ Article  │  │ Article  │        │   │
│  │   │  Card 1  │  │  Card 2  │  │  Card 3  │        │   │
│  │   └──────────┘  └──────────┘  └──────────┘        │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Categories/Tags Preview (optional)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   热门分类: [Java] [Spring Boot] [Vue] [Docker]     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 文章列表页 (Article List)

```
┌─────────────────────────────────────────────────────────────┐
│  Page Header (py-12, bg-gray-50)                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   文章                                              │   │
│  │   共 128 篇技术文章                                  │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Filter Bar (sticky top-16, bg-white/95 backdrop-blur)      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  [全部] [后端开发] [前端技术] [数据库] [DevOps]        │   │
│  │                                                     │   │
│  │  排序: [最新发布 ▼]          共 128 篇              │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Article Grid (py-8)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │   │ Article  │  │ Article  │  │ Article  │        │   │
│  │   │  Card 1  │  │  Card 2  │  │  Card 3  │        │   │
│  │   └──────────┘  └──────────┘  └──────────┘        │   │
│  │                                                     │   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │   │ Article  │  │ Article  │  │ Article  │        │   │
│  │   │  Card 4  │  │  Card 5  │  │  Card 6  │        │   │
│  │   └──────────┘  └──────────┘  └──────────┘        │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Pagination (py-8)                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         <  1  2  3  ...  10  >                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 文章详情页 (Article Detail)

```
┌─────────────────────────────────────────────────────────────┐
│  Article Header (pt-24 pb-12, bg-gradient)                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   [分类标签]                                        │   │
│  │                                                     │   │
│  │   文章标题 (text-3xl font-bold)                      │   │
│  │                                                     │   │
│  │   2026年4月4日 · 阅读 128 · 5分钟 · 1280字           │   │
│  │                                                     │   │
│  │   [标签1] [标签2] [标签3]                            │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Main Content (py-12)                                       │
│  ┌────────────────────────────────┬────────────────────┐   │
│  │                                │                    │   │
│  │   Article Content              │   TOC Sidebar      │   │
│  │   (markdown-body)              │   (sticky)         │   │
│  │                                │                    │   │
│  │   max-width: 680px             │   - 标题 1         │   │
│  │   line-height: 1.8             │   - 标题 2         │   │
│  │                                │   - 标题 3         │   │
│  │                                │                    │   │
│  └────────────────────────────────┴────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Related Articles (py-12, bg-gray-50)                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   相关文章                                          │   │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │   │ Related  │  │ Related  │  │ Related  │        │   │
│  │   └──────────┘  └──────────┘  └──────────┘        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 技术日志页 (Daily Log)

```
┌─────────────────────────────────────────────────────────────┐
│  Page Header (py-12)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   技术日志                                          │   │
│  │   记录每日技术学习与思考                              │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Timeline (py-12)                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │   ●──── 2026年4月                                   │   │
│  │   │                                                 │   │
│  │   ├── ●  4月4日  日志内容卡片...                    │   │
│  │   │                                                 │   │
│  │   ├── ●  4月3日  日志内容卡片...                    │   │
│  │   │                                                 │   │
│  │   ├── ●  4月2日  日志内容卡片...                    │   │
│  │                                                     │   │
│  │   ●──── 2026年3月                                   │   │
│  │   │                                                 │   │
│  │   ├── ●  3月28日 日志内容卡片...                    │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.5 分类页 (Categories)

```
┌─────────────────────────────────────────────────────────────┐
│  Page Header (py-12)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   文章分类                                          │   │
│  │   按主题浏览文章                                     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Category Grid (py-12)                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │   ┌─────────────┐  ┌─────────────┐               │   │
│  │   │ [Icon]      │  │ [Icon]      │               │   │
│  │   │             │  │             │               │   │
│  │   │ 后端开发     │  │ 前端技术     │               │   │
│  │   │ 32 篇文章   │  │ 28 篇文章   │               │   │
│  │   │             │  │             │               │   │
│  │   └─────────────┘  └─────────────┘               │   │
│  │                                                     │   │
│  │   ┌─────────────┐  ┌─────────────┐               │   │
│  │   │ [Icon]      │  │ [Icon]      │               │   │
│  │   │ 数据库      │  │ DevOps      │               │   │
│  │   └─────────────┘  └─────────────┘               │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.6 标签页 (Tags)

```
┌─────────────────────────────────────────────────────────────┐
│  Page Header (py-12)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   标签云                                            │   │
│  │   共 50 个标签，涵盖各种技术主题                       │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Tag Cloud (py-12)                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │    Java       Spring Boot    Vue.js               │   │
│  │         PostgreSQL     Redis    Docker            │   │
│  │    Linux        AI        Python                  │   │
│  │         TypeScript      Node.js                   │   │
│  │    Git       Kubernetes      AWS                  │   │
│  │                                                     │   │
│  │   (标签大小根据文章数量变化)                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.7 项目展示页 (Projects)

```
┌─────────────────────────────────────────────────────────────┐
│  Page Header (py-12)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   项目展示                                          │   │
│  │   个人开源项目与作品                                 │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Project Grid (py-12)                                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │   ┌──────────────┐  ┌──────────────┐             │   │
│  │   │ [Cover Img]  │  │ [Cover Img]  │             │   │
│  │   │              │  │              │             │   │
│  │   │ 项目名称      │  │ 项目名称      │             │   │
│  │   │ 描述...      │  │ 描述...      │             │   │
│  │   │ [Vue][TS]    │  │ [React][Go]  │             │   │
│  │   │ 演示  GitHub │  │ 演示  GitHub │             │   │
│  │   └──────────────┘  └──────────────┘             │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.8 关于页 (About)

```
┌─────────────────────────────────────────────────────────────┐
│  Profile Section (pt-24 pb-12)                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │              [Avatar 120x120]                       │   │
│  │                                                     │   │
│  │                博主姓名                              │   │
│  │           全栈开发工程师 | 技术博主                   │   │
│  │                                                     │   │
│  │    [GitHub] [邮箱] [Twitter]                        │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Bio Section (py-12)                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   关于我                                            │   │
│  │   ─────────────────────                             │   │
│  │   个人简介内容...                                    │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Skills Section (py-12, bg-gray-50)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   技能栈                                            │   │
│  │                                                     │   │
│  │   编程语言     ████████░░  Java                    │   │
│  │   ██████░░░░  Python                █████░░░░░  Go │   │
│  │                                                     │   │
│  │   框架         ████████░░  Spring Boot             │   │
│  │   ███████░░░  Vue.js                               │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Timeline Section (py-12)                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │   经历时间线                                        │   │
│  │                                                     │   │
│  │   2024 - 至今    XXX公司 高级开发工程师              │   │
│  │   2022 - 2024    XXX公司 中级开发工程师              │   │
│  │   2020 - 2022    XXX大学 计算机科学硕士              │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 状态设计

### 5.1 加载状态 (Loading)

```vue
<!-- 骨架屏 - 文章列表 -->
<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
  <div v-for="i in 6" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
    <el-skeleton :rows="3" animated />
  </div>
</div>

<!-- 骨架屏 - 单个卡片 -->
<div class="bg-white rounded-xl p-6 border border-gray-100">
  <el-skeleton-item variant="text" class="w-20 mb-4" />
  <el-skeleton-item variant="h3" class="mb-3" />
  <el-skeleton-item variant="text" class="mb-2" />
  <el-skeleton-item variant="text" class="w-4/5" />
</div>
```

### 5.2 空状态 (Empty)

```vue
<template>
  <div class="flex flex-col items-center justify-center py-20">
    <el-icon :size="64" class="text-gray-300 mb-4">
      <Document />
    </el-icon>
    <p class="text-gray-500 text-lg mb-2">暂无文章</p>
    <p class="text-gray-400 text-sm mb-6">开始创建你的第一篇文章吧</p>
    <button class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
      创建文章
    </button>
  </div>
</template>
```

### 5.3 错误状态 (Error)

```vue
<template>
  <div class="flex flex-col items-center justify-center py-20">
    <el-icon :size="64" class="text-red-300 mb-4">
      <CircleClose />
    </el-icon>
    <p class="text-gray-700 text-lg mb-2">加载失败</p>
    <p class="text-gray-400 text-sm mb-6">网络连接异常，请稍后重试</p>
    <button 
      class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
      @click="retry"
    >
      重新加载
    </button>
  </div>
</template>
```

---

## 6. 响应式断点

```
Breakpoint    Width       Target
─────────────────────────────────────────
sm            640px       大屏幕手机
md            768px       平板竖屏
lg            1024px      平板横屏/小笔记本
xl            1280px      笔记本/桌面
2xl           1536px      大屏幕桌面
```

### 响应式模式

```
// 网格布局
grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6

// 容器内边距
px-4 sm:px-6 lg:px-8

// 字体大小
text-2xl md:text-3xl lg:text-4xl

// 显示/隐藏
hidden md:block
md:hidden

// 布局切换
flex-col md:flex-row
```

---

## 7. 暗色模式 (Dark Mode)

```css
/* 暗色模式变量 */
.dark {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-card: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #cbd5e1;
  --text-tertiary: #94a3b8;
  --border-color: #475569;
}
```

---

## 8. 图标清单 (Element Plus Icons)

| 用途 | 图标名 |
|------|--------|
| 搜索 | Search |
| 主页 | HomeFilled |
| 文章 | Document |
| 日志 | Timer |
| 分类 | Folder |
| 标签 | CollectionTag |
| 项目 | OfficeBuilding |
| 关于 | UserFilled |
| 阅读 | View |
| 时间 | Clock |
| 日历 | Calendar |
| 链接 | Link |
| GitHub | Promotion |
| 邮箱 | Message |
| 设置 | Setting |
| 菜单 | Menu |
| 关闭 | Close |
| 返回 | ArrowLeft |
| 更多 | ArrowRight |
| 向上 | ArrowUp |
| 向下 | ArrowDown |
| 主题-亮 | Sunny |
| 主题-暗 | Moon |
| 编辑 | Edit |
| 删除 | Delete |
| 添加 | Plus |
| 刷新 | Refresh |
| 加载 | Loading |

---

## 9. 时间格式规范

**所有时间显示必须为中文格式：**

```typescript
// 完整格式
2026年4月4日 15:30:00

// 短格式
2026年4月4日

// 相对时间
刚刚
5分钟前
2小时前
昨天 14:30
3天前
2026年4月1日

// 后端返回处理
// 后端应使用 DATE_FORMAT 返回纯字符串
// 前端统一使用 formatTimeCN 工具函数
```

---

## 10. 设计检查清单

### 10.1 视觉检查
- [ ] 配色是否使用设计系统定义的颜色
- [ ] 字体大小是否符合字号阶梯
- [ ] 间距是否使用4px倍数
- [ ] 圆角是否一致
- [ ] 阴影是否适当

### 10.2 交互检查
- [ ] 所有可点击元素有hover状态
- [ ] 按钮有active/pressed反馈
- [ ] 页面切换有过渡动画
- [ ] 列表加载有stagger效果

### 10.3 状态检查
- [ ] 空状态设计完成
- [ ] 加载状态使用骨架屏
- [ ] 错误状态有重试按钮
- [ ] 成功状态有视觉反馈

### 10.4 响应式检查
- [ ] 移动端布局正常
- [ ] 平板布局正常
- [ ] 桌面端布局正常
- [ ] 字体大小随屏幕适配

### 10.5 可访问性检查
- [ ] 颜色对比度 >= 4.5:1
- [ ] 点击目标 >= 44px
- [ ] 图片有alt文本
- [ ] 表单有关联label

---

> 设计系统版本: v1.0
> 最后更新: 2026年4月4日
> 维护者: nanmuli
