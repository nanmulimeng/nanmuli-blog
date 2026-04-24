"""健康检查路由"""

from fastapi import APIRouter

router = APIRouter()

VERSION = "2.0.0"


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "web-collector-crawler",
        "version": VERSION
    }
