
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import FilestoreMeta


class FilestoreMetaHelper:
    @staticmethod
    async def insert(session: AsyncSession, filename: str, file_length: int, mimetype: str) -> FilestoreMeta:
        """

        Args:
            session:
            filename:
            file_length:
            mimetype:

        Returns: Instance created with filestore_id populated

        """
        async with session.begin_nested() as nested_transaction:
            filestore_meta: FilestoreMeta = FilestoreMeta()
            filestore_meta.filename = filename
            filestore_meta.size = file_length
            filestore_meta.mimetype = mimetype

            session.add(filestore_meta)
            await session.flush([filestore_meta])
            await nested_transaction.commit()
        return filestore_meta
