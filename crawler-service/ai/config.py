"""AI configuration — delegates to the unified Settings singleton."""

from config import settings


class AiSettings:
    """Facade that exposes AI-related fields from the unified Settings.

    Maintains backward compatibility with code that expects AiSettings instances
    (e.g., ContentOrganizer constructor, tests).
    """

    def __init__(self, *, ai_enabled=None, ai_api_key=None, ai_model=None, **_kwargs):
        self._overrides = {}
        if ai_enabled is not None:
            self._overrides["ai_enabled"] = ai_enabled
        if ai_api_key is not None:
            self._overrides["ai_api_key"] = ai_api_key
        if ai_model is not None:
            self._overrides["ai_model"] = ai_model

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._overrides:
            return self._overrides[name]

        # 优先从后端动态配置读取（AI key 等可运行时变更的配置）
        if name in ("ai_enabled", "ai_api_key", "ai_model"):
            try:
                from standalone.backend_config import get as _get
                val = _get(name.replace("_", "."))
                if val:
                    return val
            except Exception:
                pass

        return getattr(settings, name)

    @property
    def is_configured(self) -> bool:
        return (
            self.ai_enabled
            and bool(self.ai_api_key)
            and bool(self.ai_base_url)
            and bool(self.ai_model)
        )


ai_settings = AiSettings()
