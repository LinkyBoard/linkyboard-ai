"""Users 도메인 서비스

Spring Boot 사용자 동기화를 위한 비즈니스 로직 계층입니다.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.middlewares.context import get_request_id
from app.core.utils.datetime import now_utc
from app.domains.users.exceptions import UserNotFoundException
from app.domains.users.models import User
from app.domains.users.repository import UserRepository
from app.domains.users.schemas import BulkSyncResponse, UserSync

logger = get_logger(__name__)


class UserService:
    """사용자 서비스"""

    def __init__(self, session: AsyncSession):
        self.repository = UserRepository(session)

    async def get_user(self, user_id: int) -> User:
        """사용자 조회

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 객체

        Raises:
            UserNotFoundException: 사용자를 찾을 수 없는 경우
        """
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(user_id=user_id)
        return user

    async def get_users(
        self,
        page: int = 1,
        size: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[User], int]:
        """사용자 목록 조회

        Args:
            page: 페이지 번호
            size: 페이지 크기
            include_deleted: 삭제된 사용자 포함 여부

        Returns:
            (사용자 목록, 전체 사용자 수) 튜플
        """
        skip = (page - 1) * size
        users = await self.repository.get_list(
            skip=skip, limit=size, include_deleted=include_deleted
        )
        total = await self.repository.count(include_deleted=include_deleted)
        return list(users), total

    async def upsert_user(self, user_data: UserSync) -> User:
        """사용자 Upsert (생성 또는 업데이트)

        Spring Boot에서 전달받은 사용자 ID로 동기화합니다.
        - 존재하지 않으면 생성
        - 이미 존재하면 last_sync_at 업데이트
        - 삭제된 사용자는 복구 (deleted_at = NULL)

        Args:
            user_data: 사용자 동기화 데이터

        Returns:
            생성 또는 업데이트된 사용자 객체
        """
        existing = await self.repository.get_by_id(
            user_data.id, include_deleted=True
        )

        if existing:
            # 업데이트 또는 복구
            action = "restored" if existing.deleted_at else "updated"
            if existing.deleted_at:
                existing.deleted_at = None  # 복구

            existing.last_sync_at = now_utc()
            user = await self.repository.update(existing)

            logger.info(
                "User synced",
                extra={
                    "request_id": get_request_id(),
                    "user_id": user.id,
                    "action": action,
                },
            )
            return user
        else:
            # 생성
            user = User(id=user_data.id, last_sync_at=now_utc())
            created_user = await self.repository.create(user)

            logger.info(
                "User synced",
                extra={
                    "request_id": get_request_id(),
                    "user_id": created_user.id,
                    "action": "created",
                },
            )
            return created_user

    async def bulk_upsert_users(
        self, users: list[UserSync]
    ) -> BulkSyncResponse:
        """벌크 사용자 Upsert

        Args:
            users: 동기화할 사용자 목록

        Returns:
            벌크 동기화 결과
        """
        total = len(users)
        created = 0
        updated = 0
        restored = 0

        for user_data in users:
            try:
                existing = await self.repository.get_by_id(
                    user_data.id, include_deleted=True
                )

                if existing:
                    was_deleted = existing.deleted_at is not None
                    if was_deleted:
                        existing.deleted_at = None
                        restored += 1
                    else:
                        updated += 1

                    existing.last_sync_at = now_utc()
                    await self.repository.update(existing)
                else:
                    user = User(id=user_data.id, last_sync_at=now_utc())
                    await self.repository.create(user)
                    created += 1

            except Exception:
                logger.exception(
                    "Failed to sync user",
                    extra={
                        "request_id": get_request_id(),
                        "user_id": getattr(user_data, "id", None),
                    },
                )
                raise

        return BulkSyncResponse(
            total=total,
            created=created,
            updated=updated,
            restored=restored,
        )

    async def delete_user(self, user_id: int) -> None:
        """사용자 Soft Delete

        Args:
            user_id: 삭제할 사용자 ID

        Raises:
            UserNotFoundException: 사용자를 찾을 수 없는 경우
        """
        user = await self.get_user(user_id)
        await self.repository.soft_delete(user)

        logger.info(
            "User deleted",
            extra={
                "request_id": get_request_id(),
                "user_id": user_id,
                "action": "deleted",
            },
        )
