"""
Smart Routing System - 스마트 라우팅 시스템

V1 (Legacy) 와 V2 (Agent) 모드 간의 지능적 분기를 처리합니다.
"""

from .smart_router import SmartRouter, smart_router
from .legacy_adapter import LegacyAdapter, legacy_adapter

__all__ = [
    "SmartRouter",
    "smart_router",
    "LegacyAdapter", 
    "legacy_adapter"
]