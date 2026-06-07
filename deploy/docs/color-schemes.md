# Color Schemes

> 更新时间：2026-06-03
> 用途：前端视觉配色参考。MVP Beta 阶段优先保障可读性和管理效率。

---

## 推荐默认方案：Clean Tech

适合当前博客公开站点和管理后台。

```css
:root {
  --color-primary: #2563eb;
  --color-primary-hover: #1d4ed8;
  --color-accent: #0891b2;
  --color-success: #16a34a;
  --color-warning: #d97706;
  --color-danger: #dc2626;

  --bg-page: #f8fafc;
  --bg-surface: #ffffff;
  --bg-muted: #f1f5f9;

  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;

  --border-subtle: #e2e8f0;
}
```

适用场景：

- 管理后台。
- 文章列表。
- 日报列表和详情。
- 系统配置。

## Dark Reader

适合作为后续暗色模式基础。

```css
:root[data-theme="dark"] {
  --color-primary: #60a5fa;
  --color-primary-hover: #93c5fd;
  --color-accent: #22d3ee;
  --color-success: #4ade80;
  --color-warning: #fbbf24;
  --color-danger: #f87171;

  --bg-page: #020617;
  --bg-surface: #0f172a;
  --bg-muted: #1e293b;

  --text-primary: #f8fafc;
  --text-secondary: #cbd5e1;
  --text-muted: #64748b;

  --border-subtle: #334155;
}
```

适用场景：

- 夜间阅读。
- 技术日报长文阅读。
- 管理端可选主题。

## Status Colors

日报和采集任务状态建议统一颜色：

| 状态 | 颜色 | 用途 |
|------|------|------|
| pending | `#64748b` | 等待执行 |
| running | `#2563eb` | 正在执行 |
| completed | `#16a34a` | 已完成 |
| failed | `#dc2626` | 失败 |
| warning | `#d97706` | 需要关注 |

## Quality Colors

日报质量评分建议：

| 分数 | 颜色 | 说明 |
|------|------|------|
| 85-100 | `#16a34a` | 质量较高 |
| 70-84 | `#65a30d` | 可接受 |
| 60-69 | `#d97706` | 需要优化 |
| 0-59 | `#dc2626` | 不建议自动发布 |

## 不建议的方向

MVP Beta 阶段暂不建议：

- 大面积霓虹渐变背景。
- 大面积 glassmorphism。
- 过重动画和视差效果。
- 管理端使用高饱和暗色主题作为默认。
- 为了视觉效果牺牲日报和配置页面的信息密度。

后续如果要升级公开站点视觉，可以先做文章页和项目页，不要影响管理端稳定使用。
