"""Users 도메인 모델 정의

Spring Boot 서버와의 사용자 동기화를 위한 모델입니다.
ID는 Spring Boot에서 제공되며, 자동 증가하지 않습니다.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """사용자 모델 (Spring Boot 동기화용)

    Spring Boot 서버에서 생성된 사용자 정보를 동기화하여 저장합니다.
    ID는 Spring Boot에서 제공되므로 자동 증가하지 않습니다.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False,
        comment="Spring Boot에서 제공하는 사용자 ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성 일시",
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="수정 일시",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="삭제 일시 (Soft Delete)"
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="마지막 동기화 일시"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, deleted_at={self.deleted_at}, "
            f"last_sync_at={self.last_sync_at})>"
        )
