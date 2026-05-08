"""AI content organization module.

Provides OpenAI-compatible API integration for:
- Single/multi-page content organization
- Keyword optimization and expansion
- Daily digest generation
"""

from .config import AiSettings, ai_settings
from .organizer import ContentOrganizer

content_organizer = ContentOrganizer()

__all__ = ["AiSettings", "ContentOrganizer", "content_organizer"]
