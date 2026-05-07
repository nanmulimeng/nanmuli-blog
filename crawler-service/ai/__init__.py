"""AI content organization module.

Provides OpenAI-compatible API integration for:
- Single/multi-page content organization
- Keyword optimization and expansion
- Daily digest generation
"""

from .config import AiSettings
from .organizer import ContentOrganizer

__all__ = ["AiSettings", "ContentOrganizer"]
