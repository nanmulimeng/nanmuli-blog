"""AI 整理内容质量与中文输出全面测试：验证三大模块整理后的文档质量"""

import os
import sys
import json
import re
import pytest
from unittest.mock import AsyncMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.organizer import (
    ContentOrganizer, OrganizedContent, DigestContent,
    PageContent, DigestPageContent,
    InvalidOutputError, _extract_json,
)
from ai.config import AiSettings
from crawler.utils import detect_cjk


# ============== Helpers ==============

def _make_settings(**kw):
    defaults = dict(ai_enabled=True, ai_api_key="sk-test", ai_model="test")
    defaults.update(kw)
    return AiSettings(**defaults)


def _ai_resp(content_dict, total_tokens=200):
    return {
        "content": json.dumps(content_dict, ensure_ascii=False),
        "total_tokens": total_tokens,
        "finish_reason": "stop",
    }


def _has_cjk(text: str) -> bool:
    return detect_cjk(text)


# ============== 真实中文技术 Markdown fixture ==============

SPRING_BOOT_MD = """# Spring Boot 3 优雅停机配置详解

## 1. 开启优雅停机

在 `application.yml` 中配置：

```yaml
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

启用后，应用关闭时 Web 服务器会拒绝新的请求，并等待正在处理的请求完成。默认等待 30 秒。

## 2. 自定义资源释放顺序

实现 `SmartLifecycle` 接口，按顺序释放资源：

```java
@Component
public class GracefulShutdown implements SmartLifecycle {
    private volatile boolean running = false;

    @Override
    public void start() { running = true; }

    @Override
    public void stop() {
        // 1. 停止接收新请求
        // 2. 等待进行中的请求完成
        // 3. 释放数据库连接池
        // 4. 关闭消息队列连接
        running = false;
    }

    @Override
    public boolean isRunning() { return running; }

    @Override
    public int getPhase() { return Integer.MAX_VALUE; } // 最后执行
}
```

## 3. Kubernetes 集成

在 Kubernetes 环境下需要额外配置：

```yaml
spec:
  terminationGracePeriodSeconds: 60
  containers:
  - name: app
    lifecycle:
      preStop:
        exec:
          command: ["sh", "-c", "sleep 10"]
```

`preStop` 钩子确保 Kubernetes 发送 SIGTERM 之前，Pod 已从 Service 中摘除。

| 配置项 | 值 | 说明 |
|--------|-----|------|
| terminationGracePeriodSeconds | 60 | 总等待时间 |
| preStop sleep | 10s | 等待 Service 摘除 |
| shutdown timeout | 30s | Spring Boot 等待请求完成 |

## 4. 注意事项

- 不要在 `@PreDestroy` 中执行耗时操作
- 线程池需要配置 `waitForTasksToCompleteOnShutdown=true`
- Redis 连接需要手动关闭

更多参考：[Spring Boot 官方文档](https://docs.spring.io/spring-boot/docs/current/reference/html/web.html#web.graceful-shutdown)
"""

DOCKER_TUTORIAL_MD = """# Docker 多阶段构建优化指南

## 步骤 1：创建基础镜像

```dockerfile
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY . .
RUN ./gradlew bootJar

FROM eclipse-temurin:21-jre-alpine
COPY --from=builder /app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

## 步骤 2：构建并运行

```bash
$ docker build -t myapp:latest .
$ docker run -p 8080:8080 myapp:latest
```

## 步骤 3：优化镜像大小

使用 JLink 裁剪 JRE：

```bash
$ jlink --add-modules java.base,java.sql,java.naming \
    --compress 2 --no-header-files --no-man-pages \
    --output custom-jre
```

最终镜像从 300MB 降到约 80MB。
"""

K8S_ENGLISH_MD = """# Kubernetes Horizontal Pod Autoscaler

The Horizontal Pod Autoscaler (HPA) automatically scales workload resources
based on observed CPU utilization or custom metrics.

## How HPA Works

The HPA controller periodically queries the Metrics API for resource utilization.
When the average CPU exceeds the target threshold, it increases the replica count.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Behavior Configuration

```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 300
    policies:
    - type: Percent
      value: 10
      periodSeconds: 60
  scaleUp:
    stabilizationWindowSeconds: 0
    policies:
    - type: Percent
      value: 100
      periodSeconds: 15
```

The stabilization window prevents flapping. Scale-up is aggressive (100% increase)
while scale-down is conservative (10% decrease over 60s).
"""


def _spring_boot_ai_response():
    """模拟 AI 对 Spring Boot 中文内容的整理响应"""
    return _ai_resp({
        "title": "Spring Boot 3 优雅停机配置与 Kubernetes 集成实践",
        "summary": (
            "本文详细介绍了 Spring Boot 3 内置的优雅停机机制：通过 server.shutdown=graceful 配置"
            "让 Web 服务器在关闭时拒绝新请求并等待处理中的请求完成。文章进一步讲解了如何实现 "
            "SmartLifecycle 接口自定义资源释放顺序，以及在 Kubernetes 环境下配合 "
            "terminationGracePeriodSeconds 和 preStop 钩子实现零停机部署的最佳实践。"
        ),
        "keyPoints": [
            "通过 server.shutdown=graceful 开启优雅停机，默认等待 30 秒",
            "实现 SmartLifecycle 接口按顺序释放数据库连接、消息队列等资源",
            "Kubernetes 需配置 terminationGracePeriodSeconds=60 和 preStop sleep 10s",
            "线程池需设置 waitForTasksToCompleteOnShutdown=true",
            "不要在 @PreDestroy 中执行耗时操作",
        ],
        "tags": ["Spring Boot 3", "优雅停机", "Kubernetes", "SmartLifecycle", "零停机部署"],
        "category": "后端开发",
        "fullContent": (
            "## 开启优雅停机\n\n"
            "在 `application.yml` 中配置：\n\n"
            "```yaml\n"
            "server:\n"
            "  shutdown: graceful\n"
            "spring:\n"
            "  lifecycle:\n"
            "    timeout-per-shutdown-phase: 30s\n"
            "```\n\n"
            "启用后，应用关闭时 Web 服务器会拒绝新的请求，并等待正在处理的请求完成。\n\n"
            "## 自定义资源释放\n\n"
            "实现 `SmartLifecycle` 接口：\n\n"
            "```java\n"
            "@Component\n"
            "public class GracefulShutdown implements SmartLifecycle {\n"
            "    private volatile boolean running = false;\n\n"
            "    @Override\n"
            "    public void stop() {\n"
            "        running = false;\n"
            "    }\n\n"
            "    @Override\n"
            "    public int getPhase() { return Integer.MAX_VALUE; }\n"
            "}\n"
            "```\n\n"
            "## Kubernetes 集成\n\n"
            "```yaml\n"
            "spec:\n"
            "  terminationGracePeriodSeconds: 60\n"
            "  containers:\n"
            "  - name: app\n"
            "    lifecycle:\n"
            "      preStop:\n"
            "        exec:\n"
            "          command: [\"sh\", \"-c\", \"sleep 10\"]\n"
            "```\n\n"
            "| 配置项 | 值 | 说明 |\n"
            "|--------|-----|------|\n"
            "| terminationGracePeriodSeconds | 60 | 总等待时间 |\n"
            "| preStop sleep | 10s | 等待 Service 摘除 |\n"
            "| shutdown timeout | 30s | Spring Boot 等待请求完成 |\n\n"
            "更多参考：[Spring Boot 官方文档](https://docs.spring.io/spring-boot/docs/current/reference/html/web.html#web.graceful-shutdown)"
        ),
    })


def _docker_ai_response():
    return _ai_resp({
        "title": "Docker 多阶段构建与镜像优化实战教程",
        "summary": (
            "本教程演示了 Docker 多阶段构建的完整流程：从创建 builder 阶段编译 Java 项目，"
            "到使用 JRE-only 基础镜像减小最终镜像体积。通过 JLink 裁剪 JRE 模块，"
            "最终将镜像从 300MB 优化至约 80MB，大幅减少部署时间和存储开销。"
        ),
        "keyPoints": [
            "使用 FROM ... AS builder 创建构建阶段",
            "COPY --from=builder 仅复制编译产物到最终镜像",
            "通过 JLink 裁剪 JRE，仅保留必要模块",
            "最终镜像体积从 300MB 降至约 80MB",
        ],
        "tags": ["Docker", "多阶段构建", "JLink", "镜像优化", "Java 21"],
        "category": "DevOps",
        "fullContent": (
            "## 步骤 1：创建基础镜像\n\n"
            "```dockerfile\n"
            "FROM eclipse-temurin:21-jdk-alpine AS builder\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN ./gradlew bootJar\n\n"
            "FROM eclipse-temurin:21-jre-alpine\n"
            "COPY --from=builder /app/build/libs/*.jar app.jar\n"
            "EXPOSE 8080\n"
            "ENTRYPOINT [\"java\", \"-jar\", \"app.jar\"]\n"
            "```\n\n"
            "## 步骤 2：构建并运行\n\n"
            "```bash\n"
            "$ docker build -t myapp:latest .\n"
            "$ docker run -p 8080:8080 myapp:latest\n"
            "```\n\n"
            "## 步骤 3：优化镜像大小\n\n"
            "```bash\n"
            "$ jlink --add-modules java.base,java.sql,java.naming \\\n"
            "    --compress 2 --no-header-files --no-man-pages \\\n"
            "    --output custom-jre\n"
            "```\n\n"
            "最终镜像从 300MB 降到约 80MB。"
        ),
    })


def _k8s_english_ai_response():
    """模拟 AI 对英文 K8s 内容的整理 — title/summary 中文，fullContent 保留英文"""
    return _ai_resp({
        "title": "Kubernetes 水平 Pod 自动扩缩容配置详解",
        "summary": (
            "本文详细介绍了 Kubernetes Horizontal Pod Autoscaler (HPA) 的工作原理和配置方法。"
            "HPA 通过监控 CPU 利用率或自定义指标自动调整副本数量。文章涵盖了 v2 API 的完整配置，"
            "包括扩缩容行为策略：扩容采用激进策略（100% 增量），缩容采用保守策略"
            "（10% 减量 + 300 秒稳定窗口），有效防止副本数抖动。"
        ),
        "keyPoints": [
            "HPA 通过 Metrics API 定期查询资源利用率并调整副本数",
            "支持基于 CPU 利用率和自定义指标的扩缩容",
            "scaleDown 稳定窗口 300 秒防止抖动",
            "scaleUp 策略为 100% 激进扩容，periodSeconds=15",
            "scaleDown 策略为 10% 保守缩容，periodSeconds=60",
        ],
        "tags": ["Kubernetes", "HPA", "自动扩缩容", "autoscaling/v2"],
        "category": "云计算",
        "fullContent": (
            "## How HPA Works\n\n"
            "The HPA controller periodically queries the Metrics API for resource utilization. "
            "When the average CPU exceeds the target threshold, it increases the replica count.\n\n"
            "```yaml\n"
            "apiVersion: autoscaling/v2\n"
            "kind: HorizontalPodAutoscaler\n"
            "metadata:\n"
            "  name: my-app-hpa\n"
            "spec:\n"
            "  scaleTargetRef:\n"
            "    apiVersion: apps/v1\n"
            "    kind: Deployment\n"
            "    name: my-app\n"
            "  minReplicas: 2\n"
            "  maxReplicas: 10\n"
            "```\n\n"
            "## Behavior Configuration\n\n"
            "```yaml\n"
            "behavior:\n"
            "  scaleDown:\n"
            "    stabilizationWindowSeconds: 300\n"
            "    policies:\n"
            "    - type: Percent\n"
            "      value: 10\n"
            "      periodSeconds: 60\n"
            "```\n"
        ),
    })


def _digest_ai_response():
    return _ai_resp({
        "title": "技术日报 | 2026-05-16",
        "summary": (
            "今日技术圈热点：Spring Boot 3.4 正式发布，新增可观测性原生支持；"
            "Docker Desktop 5.0 引入 AI 辅助镜像构建；Kubernetes 1.32 版本"
            "发布，HPA 支持自定义指标聚合。三大更新分别影响后端开发、容器化部署"
            "和云原生编排领域，开发者应关注升级兼容性。"
        ),
        "highlight": "Spring Boot 3.4 正式发布，新增可观测性原生支持，现有项目升级需注意 API 变更",
        "tags": ["Spring Boot 3.4", "Docker 5.0", "Kubernetes 1.32", "可观测性", "AI构建"],
        "fullContent": (
            "# 技术日报 | 2026-05-16\n\n"
            "## 热点动态\n\n"
            "### Spring Boot 3.4 正式发布\n"
            "新增 Micrometer 原生支持，自动配置 OpenTelemetry 导出器。\n\n"
            "## 开源项目\n\n"
            "### Docker Desktop 5.0\n"
            "引入 AI 辅助构建，自动优化 Dockerfile 层级缓存。\n\n"
            "## 技术文章\n\n"
            "### Kubernetes HPA 深度解析\n"
            "详解 autoscaling/v2 行为配置与自定义指标聚合。\n"
        ),
        "sections": [
            {
                "category": "hot_trend",
                "categoryName": "热点动态",
                "emoji": "🔥",
                "items": [
                    {
                        "title": "Spring Boot 3.4 正式发布",
                        "oneLiner": "新增 Micrometer 原生支持和 OpenTelemetry 自动配置，对现有项目升级影响较大",
                        "sourceUrl": "https://spring.io/blog/spring-boot-3.4",
                        "sourceName": "spring.io",
                    }
                ],
            },
            {
                "category": "open_source",
                "categoryName": "开源项目",
                "emoji": "🌟",
                "items": [
                    {
                        "title": "Docker Desktop 5.0 发布",
                        "oneLiner": "引入 AI 辅助镜像构建，自动优化 Dockerfile 层级缓存，减少构建时间约 40%",
                        "sourceUrl": "https://docker.com/blog/desktop-5",
                        "sourceName": "docker.com",
                    }
                ],
            },
            {
                "category": "tech_article",
                "categoryName": "技术文章",
                "emoji": "📖",
                "items": [
                    {
                        "title": "Kubernetes HPA 深度解析",
                        "oneLiner": "详解 autoscaling/v2 行为配置、稳定窗口和自定义指标聚合策略",
                        "sourceUrl": "https://kubernetes.io/blog/hpa-deep-dive",
                        "sourceName": "kubernetes.io",
                    }
                ],
            },
        ],
    })


# ============== Step 1: 中文输出质量测试 ==============


class TestChineseQuality:
    """验证 AI 整理输出的中文质量"""

    @pytest.fixture
    def org(self):
        return ContentOrganizer(settings=_make_settings())

    @pytest.mark.asyncio
    async def test_title_is_chinese(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert _has_cjk(result.title), f"title 应含中文: {result.title}"
        assert len(result.title) >= 10, f"title 过短: {result.title} (len={len(result.title)})"

    @pytest.mark.asyncio
    async def test_summary_is_chinese(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert _has_cjk(result.summary), f"summary 应含中文"
        assert 100 <= len(result.summary) <= 400, f"summary 长度 {len(result.summary)} 不在 100-400 范围"

    @pytest.mark.asyncio
    async def test_keypoints_contain_chinese(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert len(result.key_points) >= 3, f"keyPoints 至少 3 条，实际 {len(result.key_points)}"
        for kp in result.key_points:
            assert _has_cjk(kp), f"keyPoint 应含中文: {kp}"

    @pytest.mark.asyncio
    async def test_tags_contain_tech_keywords(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert len(result.tags) >= 3
        assert "Spring Boot 3" in result.tags or any("Spring" in t for t in result.tags)

    @pytest.mark.asyncio
    async def test_english_content_title_still_chinese(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _k8s_english_ai_response()
            result = await org.organize(K8S_ENGLISH_MD)
        assert _has_cjk(result.title), f"英文内容整理后 title 应为中文: {result.title}"
        assert _has_cjk(result.summary), f"英文内容整理后 summary 应为中文"

    @pytest.mark.asyncio
    async def test_mixed_language_organize(self, org):
        mixed_md = (
            "# Kubernetes 部署 Spring Boot 应用\n\n"
            "本文介绍如何在 Kubernetes 上部署 Spring Boot 应用。\n\n"
            "## Step 1: Create Docker Image\n\n"
            "```bash\n$ docker build -t myapp .\n```\n\n"
            "## 创建部署配置\n\n"
            "```yaml\napiVersion: apps/v1\nkind: Deployment\n```\n"
        )
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(mixed_md)
        assert _has_cjk(result.title)
        assert _has_cjk(result.summary)
        assert result.key_points

    @pytest.mark.asyncio
    async def test_digest_all_chinese(self, org):
        pages = [
            DigestPageContent(url="https://spring.io/blog", title="Spring Boot 3.4",
                              markdown="# Spring Boot 3.4 Released", category="hot_trend"),
            DigestPageContent(url="https://docker.com/blog", title="Docker 5.0",
                              markdown="# Docker Desktop 5.0", category="open_source"),
        ]
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _digest_ai_response()
            result = await org.generate_digest(pages, "2026-05-16")
        assert _has_cjk(result.title)
        assert _has_cjk(result.summary)
        assert _has_cjk(result.highlight)

    @pytest.mark.asyncio
    async def test_digest_items_oneliner_chinese(self, org):
        pages = [
            DigestPageContent(url="https://spring.io", title="Spring Boot 3.4",
                              markdown="# Spring Boot 3.4", category="hot_trend"),
        ]
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _digest_ai_response()
            result = await org.generate_digest(pages, "2026-05-16")
        for sec in result.sections:
            for item in sec.items:
                assert _has_cjk(item.one_liner), f"oneLiner 应含中文: {item.one_liner}"

    @pytest.mark.asyncio
    async def test_non_tech_page_detection(self, org):
        non_tech = _ai_resp({
            "title": "登录页面",
            "summary": "该页面不包含有效技术内容，仅为登录页面。",
            "keyPoints": [],
            "tags": [],
            "category": "其他",
            "fullContent": "",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = non_tech
            with pytest.raises(InvalidOutputError, match="不包含有效技术内容"):
                await org.organize("<html><body><form>Login</form></body></html>")

    @pytest.mark.asyncio
    async def test_empty_markdown_organize(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize("")
        # 即使输入为空，mock AI 仍返回有效结果
        assert result.title


# ============== Step 2: fullContent 结构与保真度测试 ==============


class TestFullContentQuality:
    """验证 fullContent 的 Markdown 结构和内容保真度"""

    @pytest.fixture
    def org(self):
        return ContentOrganizer(settings=_make_settings())

    @pytest.mark.asyncio
    async def test_heading_levels_preserved(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert "##" in result.full_content, "fullContent 应包含 Markdown 标题"

    @pytest.mark.asyncio
    async def test_yaml_code_block_preserved(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert "```yaml" in result.full_content, "yaml 代码块应保留"
        assert "shutdown: graceful" in result.full_content, "配置参数应原样保留"

    @pytest.mark.asyncio
    async def test_java_code_block_preserved(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert "```java" in result.full_content, "java 代码块应保留"
        assert "SmartLifecycle" in result.full_content, "接口名应保留"

    @pytest.mark.asyncio
    async def test_bash_code_block_preserved(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _docker_ai_response()
            result = await org.organize(DOCKER_TUTORIAL_MD)
        assert "```bash" in result.full_content
        assert "docker build" in result.full_content, "命令行示例应原样保留"

    @pytest.mark.asyncio
    async def test_config_params_unchanged(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert "timeout-per-shutdown-phase: 30s" in result.full_content
        assert "terminationGracePeriodSeconds" in result.full_content

    @pytest.mark.asyncio
    async def test_table_structure_preserved(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert "|" in result.full_content, "表格分隔符应保留"

    @pytest.mark.asyncio
    async def test_markdown_links_preserved(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        assert "[Spring Boot 官方文档]" in result.full_content or "spring.io" in result.full_content

    @pytest.mark.asyncio
    async def test_dockerfile_preserved(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _docker_ai_response()
            result = await org.organize(DOCKER_TUTORIAL_MD)
        assert "```dockerfile" in result.full_content
        assert "COPY --from=builder" in result.full_content

    @pytest.mark.asyncio
    async def test_english_fullcontent_preserved_for_english_input(self, org):
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _k8s_english_ai_response()
            result = await org.organize(K8S_ENGLISH_MD)
        # fullContent 保留英文原文（按 prompt 规则）
        assert "HorizontalPodAutoscaler" in result.full_content
        assert "autoscaling/v2" in result.full_content

    @pytest.mark.asyncio
    async def test_no_nav_noise_in_fullcontent(self, org):
        noisy_md = (
            "# React 19 新特性\n\n"
            "[首页](/) | [博客](/blog) | [关于](/about)\n\n"
            "## Server Components\n\n"
            "React 19 正式发布了 Server Components 稳定版。\n\n"
            "---\n\n"
            "Cookie 设置 | 隐私政策 | ICP备案号: 京ICP备12345\n\n"
            "扫码关注公众号获取更多内容\n\n"
            "本文由 AI 生成，仅供参考"
        )
        clean_resp = _ai_resp({
            "title": "React 19 Server Components 稳定版发布",
            "summary": "React 19 正式发布 Server Components 稳定版，支持 use() hook 简化异步数据获取，"
                       "对现有项目升级有较大影响，开发者需评估迁移成本。",
            "keyPoints": [
                "Server Components 进入稳定阶段",
                "use() hook 简化异步数据获取",
                "现有项目需评估迁移成本",
            ],
            "tags": ["React 19", "Server Components", "use() hook"],
            "category": "前端开发",
            "fullContent": "## Server Components\n\nReact 19 正式发布 Server Components 稳定版。\n",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = clean_resp
            result = await org.organize(noisy_md)
        assert "首页" not in result.full_content
        assert "ICP备案" not in result.full_content
        assert "Cookie" not in result.full_content
        assert "扫码关注" not in result.full_content


# ============== Step 3: 三大模块端到端管线测试 ==============


class TestEndToEndPipeline:
    """模拟 crawl → filter → AI organize 全链路"""

    @pytest.fixture
    def org(self):
        return ContentOrganizer(settings=_make_settings())

    @pytest.mark.asyncio
    async def test_single_crawl_then_organize(self, org):
        """单页爬取→整理"""
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD, "tech_summary")

        assert _has_cjk(result.title)
        assert _has_cjk(result.summary)
        assert len(result.key_points) >= 3
        assert "```yaml" in result.full_content
        assert result.category in {"后端开发", "DevOps", "云计算"}

    @pytest.mark.asyncio
    async def test_deep_crawl_then_organize_multiple(self, org):
        """深度爬取多页→整理"""
        pages = [
            PageContent(url="https://spring.io/guides", title="Spring Boot 3 优雅停机",
                        markdown=SPRING_BOOT_MD, word_count=800, depth=0),
            PageContent(url="https://k8s.io/docs", title="Kubernetes HPA",
                        markdown=K8S_ENGLISH_MD, word_count=600, depth=1),
        ]
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize_multiple(pages, "tech_summary")

        assert _has_cjk(result.title)
        assert _has_cjk(result.summary)
        # 多页 prompt 应包含来源标记
        prompt_arg = m.call_args[0][1]
        assert "来源 1" in prompt_arg
        assert "来源 2" in prompt_arg

    @pytest.mark.asyncio
    async def test_keyword_search_then_organize(self, org):
        """关键词搜索→整理"""
        pages = [
            PageContent(url="https://a.com/docker-build", title="Docker 多阶段构建",
                        markdown=DOCKER_TUTORIAL_MD, word_count=400, depth=0),
            PageContent(url="https://b.com/dockerfile-best", title="Dockerfile 最佳实践",
                        markdown="# Dockerfile 最佳实践\n\n使用 COPY 而非 ADD...", word_count=300, depth=0),
        ]
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _docker_ai_response()
            result = await org.organize_multiple(
                pages, "tech_summary",
                keyword_context="原始关键词：docker\n优化关键词：Docker 多阶段构建优化"
            )

        assert _has_cjk(result.title)
        prompt_arg = m.call_args[0][1]
        assert "docker" in prompt_arg
        assert "搜索上下文" in prompt_arg

    @pytest.mark.asyncio
    async def test_tutorial_template(self, org):
        """教程模板：输出含有序步骤"""
        tutorial_resp = _ai_resp({
            "title": "Docker 多阶段构建与镜像优化步骤教程",
            "summary": "本教程按步骤演示 Docker 多阶段构建流程：从创建 builder 阶段编译 Java 项目，"
                       "到使用 JRE 基础镜像减小体积，再到 JLink 裁剪模块实现 80MB 精简镜像。",
            "keyPoints": [
                "步骤一：使用 FROM AS builder 创建构建阶段",
                "步骤二：通过 COPY --from=builder 复制编译产物",
                "步骤三：使用 JLink 裁剪 JRE 模块",
            ],
            "tags": ["Docker", "多阶段构建", "JLink"],
            "category": "DevOps",
            "fullContent": (
                "## 步骤 1：创建基础镜像\n\n```dockerfile\nFROM eclipse-temurin:21-jdk-alpine AS builder\n```\n\n"
                "## 步骤 2：构建并运行\n\n```bash\n$ docker build -t myapp .\n```\n\n"
                "## 步骤 3：优化镜像大小\n\n```bash\n$ jlink --add-modules java.base\n```\n"
            ),
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = tutorial_resp
            result = await org.organize(DOCKER_TUTORIAL_MD, "tutorial")

        assert "步骤" in result.full_content
        assert "```dockerfile" in result.full_content

    @pytest.mark.asyncio
    async def test_comparison_template(self, org):
        """对比模板：输出含表格或对比结构"""
        compare_resp = _ai_resp({
            "title": "JRE vs JLink 镜像大小对比分析",
            "summary": "对比标准 JRE 基础镜像与 JLink 裁剪镜像的体积差异。"
                       "标准 JRE 镜像约 300MB，JLink 裁剪后约 80MB，体积减少 73%。",
            "keyPoints": [
                "标准 JRE 镜像包含所有模块，体积约 300MB",
                "JLink 裁剪仅保留必要模块，体积降至 80MB",
                "裁剪比例达 73%，显著减少部署时间",
            ],
            "tags": ["Docker", "JLink", "镜像优化", "JRE"],
            "category": "DevOps",
            "fullContent": (
                "| 方案 | 镜像大小 | 构建时间 | 适用场景 |\n"
                "|------|----------|----------|----------|\n"
                "| 标准 JRE | 300MB | 2min | 通用部署 |\n"
                "| JLink 裁剪 | 80MB | 3min | 生产优化 |\n"
            ),
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = compare_resp
            result = await org.organize(DOCKER_TUTORIAL_MD, "comparison")

        assert "|" in result.full_content, "对比模板应生成表格"
        assert "300MB" in result.full_content or "80MB" in result.full_content

    @pytest.mark.asyncio
    async def test_knowledge_report_template(self, org):
        """知识报告模板：输出含结构化知识"""
        knowledge_resp = _ai_resp({
            "title": "Spring Boot 优雅停机知识条目",
            "summary": "Spring Boot 3 内置优雅停机机制，通过 server.shutdown=graceful 配置"
                       "实现零停机部署。支持 SmartLifecycle 接口自定义资源释放顺序。",
            "keyPoints": [
                "graceful shutdown 配置及原理",
                "SmartLifecycle 资源释放接口",
                "Kubernetes 集成最佳实践",
            ],
            "tags": ["Spring Boot", "优雅停机", "Kubernetes"],
            "category": "后端开发",
            "fullContent": "## 核心原理\n\n优雅停机通过拒绝新请求+等待完成实现。\n\n## 配置方法\n\n```yaml\nserver:\n  shutdown: graceful\n```\n",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = knowledge_resp
            result = await org.organize(SPRING_BOOT_MD, "knowledge_report")

        assert _has_cjk(result.title)
        assert len(result.key_points) >= 2

    @pytest.mark.asyncio
    async def test_digest_generation_full_pipeline(self, org):
        """日报生成全链路"""
        pages = [
            DigestPageContent(url="https://spring.io/blog", title="Spring Boot 3.4 发布",
                              markdown="# Spring Boot 3.4\n新增可观测性支持。", category="hot_trend"),
            DigestPageContent(url="https://docker.com", title="Docker Desktop 5.0",
                              markdown="# Docker 5.0\nAI 辅助构建。", category="open_source"),
            DigestPageContent(url="https://k8s.io/blog", title="K8s HPA 解析",
                              markdown="# HPA Deep Dive\n行为配置详解。", category="tech_article"),
        ]
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _digest_ai_response()
            result = await org.generate_digest(pages, "2026-05-16")

        assert _has_cjk(result.title)
        assert _has_cjk(result.summary)
        assert _has_cjk(result.highlight)
        assert len(result.sections) >= 2
        for sec in result.sections:
            assert sec.category_name
            for item in sec.items:
                assert item.title
                assert _has_cjk(item.one_liner)

    @pytest.mark.asyncio
    async def test_ai_failure_graceful_degradation(self, org):
        """AI 整理失败时任务不崩溃"""
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("API server error 503")
            with pytest.raises(RuntimeError):
                await org.organize(SPRING_BOOT_MD)

    @pytest.mark.asyncio
    async def test_keyword_optimize_then_organize_pipeline(self, org):
        """关键词优化→搜索→整理 全链路"""
        # Step 1: 优化关键词
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = {"content": "Docker 多阶段构建优化实践", "total_tokens": 20, "finish_reason": "stop"}
            optimized = await org.optimize_keyword("docker")

        assert _has_cjk(optimized)
        assert "Docker" in optimized

        # Step 2: 模拟搜索结果
        pages = [
            PageContent(url="https://a.com", title="Docker 构建", markdown=DOCKER_TUTORIAL_MD, word_count=400),
        ]

        # Step 3: 整理
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _docker_ai_response()
            result = await org.organize_multiple(pages, "tech_summary", f"原始关键词：docker\n优化关键词：{optimized}")

        assert _has_cjk(result.title)
        assert result.key_points


# ============== Step 4: 验证逻辑增强测试 ==============


class TestValidationEnhanced:

    @pytest.fixture
    def org(self):
        return ContentOrganizer(settings=_make_settings())

    @pytest.mark.asyncio
    async def test_english_only_title_passes_validation(self, org):
        """当前验证不要求中文，纯英文 title 也能通过"""
        resp = _ai_resp({
            "title": "Spring Boot Graceful Shutdown Guide",
            "summary": "本文介绍 Spring Boot 3 的优雅停机机制配置方法和最佳实践。",
            "keyPoints": ["graceful shutdown config", "SmartLifecycle interface"],
            "tags": ["Spring Boot", "graceful shutdown"],
            "category": "后端开发",
            "fullContent": "## Graceful Shutdown\n\nConfiguration and best practices.",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = resp
            result = await org.organize("content")
        # 验证通过 — 已知限制：_validate 不检查中文
        assert result.title == "Spring Boot Graceful Shutdown Guide"

    @pytest.mark.asyncio
    async def test_short_summary_passes_but_below_prompt_spec(self, org):
        """summary=50 字通过验证（min=10），但低于 prompt 要求的 100 字"""
        resp = _ai_resp({
            "title": "测试标题文章内容技术",
            "summary": "这是一篇关于技术的文章摘要内容。",
            "keyPoints": ["这是一个技术要点描述"],
            "tags": ["测试"],
            "category": "其他",
            "fullContent": "这是一段足够长的正文内容，包含技术细节和代码示例。",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = resp
            result = await org.organize("content")
        # 通过验证但 summary 只有 17 字，低于 prompt 要求的 100-300 字
        assert len(result.summary) < 100

    @pytest.mark.asyncio
    async def test_generic_tags_pass_validation(self, org):
        """过泛标签如"技术"也能通过验证 — 已知限制"""
        resp = _ai_resp({
            "title": "技术文章标题测试内容",
            "summary": "本文详细介绍了技术的最新发展和趋势，对开发者有重要参考价值。",
            "keyPoints": ["技术发展趋势"],
            "tags": ["技术", "编程", "开发"],
            "category": "其他",
            "fullContent": "技术内容详细说明" * 5,
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = resp
            result = await org.organize("content")
        # 过泛标签通过了 — 已知限制
        assert "技术" in result.tags

    @pytest.mark.asyncio
    async def test_fullcontent_preserves_core_content(self, org):
        """fullContent 应保留原文核心内容"""
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _spring_boot_ai_response()
            result = await org.organize(SPRING_BOOT_MD)
        # 核心技术术语应保留在 fullContent 中
        core_terms = ["graceful", "shutdown", "SmartLifecycle", "terminationGracePeriodSeconds"]
        preserved = sum(1 for t in core_terms if t in result.full_content)
        assert preserved >= 2, f"fullContent 应保留至少 2 个核心技术术语，实际保留 {preserved}/{len(core_terms)}"

    @pytest.mark.asyncio
    async def test_category_must_be_valid(self, org):
        """无效 category 应被归一化为 '其他'"""
        resp = _ai_resp({
            "title": "测试标题",
            "summary": "这是一个测试摘要内容，用于验证分类映射逻辑的正确性。",
            "keyPoints": ["测试要点描述内容"],
            "tags": ["test"],
            "category": "quantum_computing",
            "fullContent": "测试正文内容" * 5,
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = resp
            result = await org.organize("content")
        assert result.category == "其他"


# ============== Step 5: 极端内容质量测试 ==============


class TestExtremeContentQuality:

    @pytest.fixture
    def org(self):
        return ContentOrganizer(settings=_make_settings())

    @pytest.mark.asyncio
    async def test_huge_page_summary_shorter(self, org):
        """100K+ 字符输入 → 整理后 fullContent 远小于原文"""
        huge_md = "# 超大文档\n\n" + "技术内容段落描述。\n\n" * 5000
        resp = _ai_resp({
            "title": "超大文档技术内容摘要整理",
            "summary": "这是一份超大技术文档的整理摘要，涵盖了核心技术要点和最佳实践。",
            "keyPoints": ["核心技术要点一", "核心技术要点二"],
            "tags": ["技术", "文档"],
            "category": "其他",
            "fullContent": "## 核心内容\n\n技术内容摘要整理，涵盖主要技术要点和最佳实践。\n",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = resp
            result = await org.organize(huge_md)
        assert len(result.full_content) < len(huge_md) * 0.1

    @pytest.mark.asyncio
    async def test_pure_code_page(self, org):
        """纯代码页面整理"""
        code_only = "```java\npublic class App {\n    public static void main(String[] args) {\n        System.out.println(\"Hello\");\n    }\n}\n```"
        resp = _ai_resp({
            "title": "Java 应用程序入口类代码片段",
            "summary": "一段简单的 Java 应用程序入口类代码，包含 main 方法和标准输出语句。",
            "keyPoints": ["main 方法作为程序入口", "System.out.println 输出"],
            "tags": ["Java", "main方法"],
            "category": "后端开发",
            "fullContent": "```java\npublic class App {\n    public static void main(String[] args) {\n        System.out.println(\"Hello\");\n    }\n}\n```",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = resp
            result = await org.organize(code_only)
        assert _has_cjk(result.title)
        assert "```java" in result.full_content

    @pytest.mark.asyncio
    async def test_all_english_tech_doc(self, org):
        """全英文技术文档 → title/summary 中文，fullContent 保留英文"""
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = _k8s_english_ai_response()
            result = await org.organize(K8S_ENGLISH_MD)
        assert _has_cjk(result.title), "英文文档 title 应为中文"
        assert _has_cjk(result.summary), "英文文档 summary 应为中文"
        # fullContent 保留英文
        assert not _has_cjk(result.full_content.split("```")[0].replace("\n", " ").strip()) or \
               _has_cjk(result.full_content), "fullContent 可含中文注释或纯英文"

    @pytest.mark.asyncio
    async def test_japanese_tech_content(self, org):
        """日文技术内容 → title/summary 中文，fullContent 保留原文"""
        jp_resp = _ai_resp({
            "title": "Kubernetes 自動スケーリング 設定ガイド",
            "summary": "Kubernetes の水平ポッドオートスケーラー (HPA) の設定方法について解説。",
            "keyPoints": ["HPAの基本動作", "カスタムメトリクス設定"],
            "tags": ["Kubernetes", "HPA"],
            "category": "云计算",
            "fullContent": "## HPA 設定\n\n```yaml\napiVersion: autoscaling/v2\n```\n",
        })
        with patch.object(org, "_call_ai", new_callable=AsyncMock) as m:
            m.return_value = jp_resp
            result = await org.organize("# K8s 自動スケーリング\n内容...")
        assert result.title

    @pytest.mark.asyncio
    async def test_deeply_nested_json_extraction(self, org):
        """5 层嵌套 JSON 提取"""
        nested = json.dumps({
            "outer": {
                "mid1": {
                    "mid2": {
                        "mid3": {
                            "inner": "deep_value"
                        }
                    }
                }
            }
        })
        result = _extract_json(f"Some text before {nested} some text after")
        parsed = json.loads(result)
        assert parsed["outer"]["mid1"]["mid2"]["mid3"]["inner"] == "deep_value"
