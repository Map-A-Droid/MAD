from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Route


class RouteHelper:
    @staticmethod
    async def get(session: AsyncSession, route_id: str) -> Optional[Route]:
        stmt = select(Route).where(Route.route_id == route_id)
        result = await session.execute(stmt)
        return result.scalars().first()
