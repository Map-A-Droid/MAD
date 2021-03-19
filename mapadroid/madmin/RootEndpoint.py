from typing import Optional

from aiohttp import web
from aiohttp.abc import Request
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mad_apk import AbstractAPKStorage


class RootEndpoint(web.View):
    # TODO: Add security etc in here (abstract) to enforce security true/false
    # If we really need more methods, we can just define them abstract...
    def __init__(self, request: Request):
        super().__init__(request)
        self._commit_trigger: bool = False
        self._session: Optional[AsyncSession] = None

    async def _iter(self):
        db_wrapper: DbWrapper = self._get_db_wrapper()
        async with db_wrapper as session:
            self._session = session
            with logger.contextualize(ip=self._get_request_address(), name="endpoint"):
                response = await self.__generate_response(session)
            return response

    async def __generate_response(self, session: AsyncSession):
        try:
            logger.debug("Waiting for response to {}", self.request.url)
            response = await super()._iter()
            logger.success("Got response to {}", self.request.url)
            if self._commit_trigger:
                logger.debug("Awaiting commit")
                await session.commit()
                logger.info("Done committing")
            # else:
            #    await session.rollback()
        except Exception as e:
            logger.warning("Exception occurred in request!. Details: " + str(e))
            logger.exception("Issue with request to {}", self.request.url)
            await session.rollback()
            # TODO: Get previous URL...
            raise web.HTTPFound("/")
        return response

    def _get_request_address(self) -> str:
        if "CF-Connecting-IP" in self.request.headers:
            address = self.request.headers["CF-Connecting-IP"]
        elif "X-Forwarded-For" in self.request.headers:
            address = self.request.headers["X-Forwarded-For"]
        else:
            address = self.request.remote
        return address

    async def _redirect(self, redirect_to: str, session: AsyncSession, commit: bool = False):
        if commit:
            await session.commit()
        else:
            await session.rollback()
        raise web.HTTPFound(redirect_to)

    def _get_db_wrapper(self) -> DbWrapper:
        return self.request.app['db_wrapper']

    def _get_storage_obj(self) -> AbstractAPKStorage:
        return self.request.app['storage_obj']
