"""AI configuration — delegates to the unified Settings singleton."""

import logging

from config import settings

logger = logging.getLogger(__name__)


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
        for key, value in _kwargs.items():
            if key.startswith("ai_") and value is not None:
                self._overrides[key] = value

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._overrides:
            return self._overrides[name]

        # 所有 ai_* 字段优先从后端动态配置读取
        if name.startswith("ai_"):
            try:
                from standalone.backend_config import get as _get
                val = _get(name.replace("_", ".", 1))
                if val is not None:
                    field_type = type(getattr(settings, name))
                    if field_type is bool:
                        return val.lower() in ("true", "1", "yes", "on")
                    return field_type(val)
            except Exception as e:
                logger.debug("[AiSettings] Backend config cast failed for %s: %s", name, e)

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
