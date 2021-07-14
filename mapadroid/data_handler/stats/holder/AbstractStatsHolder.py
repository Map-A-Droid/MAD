from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession


class AbstractStatsHolder(ABC):
    @abstractmethod
    async def submit(self, session: AsyncSession) -> None:
        pass
