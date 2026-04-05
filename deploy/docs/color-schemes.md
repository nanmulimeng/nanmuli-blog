# 主题配色方案说明

## 已配置的配色方案

### 1. 🌌 赛博朋克 (Cyberpunk)
**风格**: 高对比霓虹色
- **主色**: 霓虹粉 `#ff00ff`
- **副色**: 霓虹青 `#00ffff`
- **强调**: 霓虹黄 `#ffff00`
- **Light背景**: 深色模式专用
- **Dark背景**: 纯黑 `#0a0a0f`
- **适用场景**: 科技感展示、极客风格

```css
--theme-gradient: linear-gradient(135deg, #ff00ff 0%, #00ffff 100%);
```

---

### 2. 🌊 沉稳深蓝 (Deep)
**风格**: 商务专业，沉稳大气
- **主色**: 深海蓝 `#1e3a5f`
- **副色**: 明亮蓝 `#2563eb`
- **强调**: 天蓝 `#3b82f6`
- **Light背景**: 浅灰蓝 `#f8fafc`
- **Dark背景**: 深 slate `#0f172a`
- **适用场景**: 企业官网、技术文档

```css
--theme-gradient: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
```

---

### 3. 🌙 极致暗夜 (Midnight)
**风格**: 纯黑背景配暗紫强调
- **主色**: 紫色 `#7c3aed`
- **副色**: 亮紫 `#a855f7`
- **强调**: 粉紫 `#c084fc`
- **Light背景**: 近白 `#fafafa`
- **Dark背景**: 纯黑 `#000000`
- **适用场景**: 沉浸式阅读、夜间模式

```css
--theme-gradient: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
```

---

### 4. 🐋 海洋蓝 (Ocean)
**风格**: 清新自然
- **主色**: 青蓝 `#0891b2`
- **副色**: 湖蓝 `#06b6d4`
- **强调**: 浅青 `#22d3ee`
- **Light背景**: 极浅青 `#f0fdff`
- **Dark背景**: 深青 `#083344`
- **适用场景**: 清新风格、环保主题

```css
--theme-gradient: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%);
```

---

### 5. 🌲 森林绿 (Forest)
**风格**: 自然生机
- **主色**: 墨绿 `#059669`
- **副色**: 翠绿 `#10b981`
- **强调**: 浅绿 `#34d399`
- **Light背景**: 极浅绿 `#f0fdf4`
- **Dark背景**: 深绿 `#022c22`
- **适用场景**: 自然主题、健康应用

```css
--theme-gradient: linear-gradient(135deg, #059669 0%, #10b981 100%);
```

---

### 6. 🌅 日落橙 (Sunset)
**风格**: 温暖活力
- **主色**: 深橙 `#ea580c`
- **副色**: 亮橙 `#f97316`
- **强调**: 浅橙 `#fb923c`
- **Light背景**: 极浅橙 `#fff7ed`
- **Dark背景**: 深棕 `#431407`
- **适用场景**: 活力展示、创意作品

```css
--theme-gradient: linear-gradient(135deg, #ea580c 0%, #f97316 100%);
```

---

### 7. 💜 极光紫 (Aurora) - 默认
**风格**: 梦幻极光渐变
- **主色**: 紫色 `#a855f7`
- **副色**: 粉色 `#ec4899`
- **强调**: 青色 `#00d4ff`
- **Light背景**: 浅灰 `#fafafa`
- **Dark背景**: 深黑 `#0a0a0f`
- **适用场景**: 默认风格、通用场景

```css
--theme-gradient: linear-gradient(135deg, #a855f7 0%, #ec4899 100%);
```

---

### 8. ⬛ 极简黑白 (Minimal)
**风格**: 纯粹极简
- **主色**: 近黑 `#171717`
- **副色**: 中灰 `#404040`
- **强调**: 浅灰 `#525252`
- **Light背景**: 纯白 `#ffffff`
- **Dark背景**: 纯黑 `#000000`
- **适用场景**: 极简主义、设计作品集

```css
--theme-gradient: linear-gradient(135deg, #171717 0%, #404040 100%);
```

---

## 显示模式

| 模式 | 说明 |
|------|------|
| 🌞 浅色 | 强制使用 Light 主题配色 |
| 🌓 自动 | 跟随系统偏好自动切换 |
| 🌙 深色 | 强制使用 Dark 主题配色 |

---

## 使用方法

### 1. 在导航栏切换主题
点击顶部导航栏的调色盘图标，即可打开主题面板进行切换。

### 2. 在代码中切换主题

```typescript
import { setTheme, setThemeMode } from '@/styles/themes'

// 切换配色方案
setTheme('cyberpunk')  // 赛博朋克
setTheme('deep')       // 沉稳深蓝
setTheme('midnight')   // 极致暗夜

// 切换显示模式
setThemeMode('light')  // 浅色
setThemeMode('dark')   // 深色
setThemeMode('auto')   // 自动
```

### 3. 在组件中使用主题变量

```vue
<template>
  <div class="text-theme-primary bg-theme-bg-primary">
    <!-- 使用 Tailwind 类 -->
  </div>
</template>

<style scoped>
.custom-element {
  color: var(--theme-primary);
  background: var(--theme-bg-primary);
  border: 1px solid var(--theme-glass-border);
}
</style>
```

---

## 推荐搭配

| 场景 | 推荐配色 | 推荐模式 |
|------|----------|----------|
| 技术博客 | Deep / Aurora | Dark |
| 设计作品 | Sunset / Aurora | Light |
| 极客风格 | Cyberpunk | Dark |
| 商务官网 | Deep / Minimal | Light |
| 夜间阅读 | Midnight | Dark |
| 自然主题 | Forest / Ocean | Light |
