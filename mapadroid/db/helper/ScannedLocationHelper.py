from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import Scannedlocation
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.s2Helper import S2Helper


class ScannedLocationHelper:
    @staticmethod
    async def get(session: AsyncSession, cell_id: int) -> Optional[Scannedlocation]:
        stmt = select(Scannedlocation).where(Scannedlocation.cellid == cell_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def set_scanned_location(session: AsyncSession, lat: float, lng: float, _timestamp: float) -> None:
        """
        Update scannedlocation of a given lat/lng.
        Immediately calls insert/update accordingly (without committing!)
        """
        # TODO: https://docs.sqlalchemy.org/en/14/changelog/migration_12.html#support-for-insert-on-duplicate-key-update
        #  Would it make more sense to simply create the query and run it?
        cell_id = int(S2Helper.lat_lng_to_cell_id(float(lat), float(lng), 16))
        scanned_location: Optional[Scannedlocation] = await ScannedLocationHelper.get(session, cell_id)
        if not scanned_location:
            scanned_location: Scannedlocation = Scannedlocation()
            scanned_location.cellid = cell_id
        scanned_location.latitude = lat
        scanned_location.longitude = lng
        scanned_location.last_modified = DatetimeWrapper.fromtimestamp(_timestamp)
        scanned_location.done = True
        scanned_location.band1 = -1
        scanned_location.band2 = -1
        scanned_location.band3 = -1
        scanned_location.band4 = -1
        scanned_location.band5 = -1
        scanned_location.midpoint = -1
        scanned_location.width = 0
        session.add(scanned_location)
