import asyncio
import json
import socket
from abc import ABC
from typing import Any, Optional, Dict, Union, Tuple

from aiohttp import web
from aiohttp.abc import Request
from aiohttp.helpers import sentinel
from aiohttp.typedefs import LooseHeaders, StrOrURL
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.model import Base, AutoconfigRegistration, AutoconfigLog
from mapadroid.mad_apk.abstract_apk_storage import AbstractAPKStorage
from mapadroid.mad_apk.apk_enums import APKArch, APKType, APKPackage
from mapadroid.mad_apk.utils import convert_to_backend
from mapadroid.madmin import apiException
from mapadroid.mapping_manager.MappingManager import MappingManager
from mapadroid.utils.authHelper import check_auth
from mapadroid.utils.json_encoder import MADEncoder
from mapadroid.utils.updater import DeviceUpdater


class AbstractMitmReceiverRootEndpoint(web.View, ABC):
    # TODO: Add security etc in here (abstract) to enforce security true/false
    # If we really need more methods, we can just define them abstract...
    def __init__(self, request: Request):
        super().__init__(request)
        self._commit_trigger: bool = False
        self._session: Optional[AsyncSession] = None
        if self._get_mad_args().madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._identifier = None

    async def _iter(self):
        with logger.contextualize(ip=self._get_request_address(), name="endpoint"):
            await self._check_mitm_device_auth()

            db_wrapper: DbWrapper = self._get_db_wrapper()
            async with db_wrapper as session, session:
                self._session = session
                response = await self.__generate_response(session)
                return response

    async def __generate_response(self, session: AsyncSession):
        try:
            # logger.debug("Waiting for response to {}", self.request.url)
            response = await super()._iter()
            # logger.success("Got response to {}", self.request.url)
            if self._commit_trigger:
                # logger.debug("Awaiting commit")
                await session.commit()
                # logger.info("Done committing")
            else:
                await session.rollback()
        except web.HTTPFound as e:
            raise e
        except Exception as e:
            logger.warning("Exception occurred in request!. Details: " + str(e))
            logger.exception("Issue with request to {}", self.request.url)
            await session.rollback()
            # TODO: Get previous URL...
            raise web.HTTPFound("/")
        return response

    def _save(self, instance: Base):
        """
        Creates or updates
        :return:
        """
        self._commit_trigger = True
        self._session.add(instance)
        # await self._session.flush(instance)

    async def _delete(self, instance: Base):
        """
        Deletes the instance from the DB
        :param instance:
        :return:
        """
        self._commit_trigger = True
        await self._session.delete(instance)

    def _get_request_address(self) -> str:
        if "CF-Connecting-IP" in self.request.headers:
            addresses = self.request.headers["CF-Connecting-IP"].split(",")
        elif "X-Forwarded-For" in self.request.headers:
            addresses = self.request.headers["X-Forwarded-For"].split(",")
        elif "HTTP_X_REAL_IP" in self.request.headers:
            addresses = self.request.headers["HTTP_X_REAL_IP"].split(",")
        elif "HTTP_X_FORWARDED_FOR" in self.request.headers:
            addresses = self.request.headers["HTTP_X_FORWARDED_FOR"].split(",")[0].split(',')
        else:
            addresses = [self.request.remote]
        for ip in addresses:
            try:
                socket.inet_aton(ip)
                return ip
            except socket.error:
                pass
        # No IPv4 address found.  Return the first value
        return addresses[0]

    async def _add_notice_message(self, message: str) -> None:
        # TODO: Handle accordingly
        # session = await get_session(self.request)
        # session["notice"] = message
        pass

    async def _redirect(self, redirect_to: StrOrURL, commit: bool = False):
        if commit:
            await self._session.commit()
        else:
            await self._session.rollback()
        raise web.HTTPFound(redirect_to)

    def _get_db_wrapper(self) -> DbWrapper:
        return self.request.app['db_wrapper']

    def _get_mad_args(self):
        return self.request.app['mad_args']

    def _get_mapping_manager(self) -> MappingManager:
        return self.request.app['mapping_manager']

    def _get_mitm_mapper(self) -> MitmMapper:
        return self.request.app['mitm_mapper']

    def _get_mitmreceiver_startup_time(self) -> int:
        return self.request.app["mitmreceiver_startup_time"]

    def _get_data_queue(self) -> asyncio.Queue:
        return self.request.app["data_queue"]

    def _get_storage_obj(self) -> AbstractAPKStorage:
        return self.request.app['storage_obj']

    @staticmethod
    def _convert_to_json_string(content) -> str:
        try:
            return json.dumps(content, cls=MADEncoder)
        except Exception as err:
            raise apiException.FormattingError(err)

    def _get_instance_id(self) -> int:
        db_wrapper: DbWrapper = self._get_db_wrapper()
        return db_wrapper.get_instance_id()

    def _get_device_updater(self) -> DeviceUpdater:
        return self.request.app['device_updater']

    @staticmethod
    def _json_response(data: Any = sentinel, *, text: Optional[str] = None, body: Optional[bytes] = None,
                       status: int = 200, reason: Optional[str] = None, headers: Optional[LooseHeaders] = None,
                       content_type: str = "application/json") -> web.Response:
        if data is not sentinel:
            if text or body:
                raise ValueError("only one of data, text, or body should be specified")
            else:
                text = json.dumps(data, indent=None, cls=MADEncoder)
        return web.Response(
            text=text,
            body=body,
            status=status,
            reason=reason,
            headers=headers,
            content_type=content_type,
        )

    def _url_for(self, path_name: str, query: Optional[Dict] = None, dynamic_path: Optional[Dict] = None):
        if dynamic_path is None:
            dynamic_path = {}
        if query is None:
            query = {}
        return self.request.app.router[path_name].url_for(**dynamic_path).with_query(query)

    def _parse_frontend(self) -> Union[Tuple[APKType, APKArch], web.Response]:
        """ Converts front-end input into backend enums
        Returns (tuple):
            Returns a tuple of (APKType, APKArch) enums or a flask.Response stating what is invalid
        """
        apk_type_o = self.request.match_info.get('apk_type')
        apk_arch_o = self.request.match_info.get('apk_arch')
        package, architecture = convert_to_backend(apk_type_o, apk_arch_o)
        if apk_type_o is not None and package is None:
            resp_msg = 'Invalid Type.  Valid types are {}'.format([e.name for e in APKPackage])
            return web.Response(status=404, body=resp_msg)
        if architecture is None and apk_arch_o is not None:
            resp_msg = 'Invalid Architecture.  Valid types are {}'.format([e.name for e in APKArch])
            return web.Response(status=404, body=resp_msg)
        return package, architecture

    async def autoconfig_log(self, **kwargs) -> None:
        session_id: Optional[int] = kwargs.get('session_id', None)
        try:
            level = kwargs['level']
            msg = kwargs['msg']
        except KeyError:
            level, msg = str(await self.request.read(), 'utf-8').split(',', 1)

        autoconfig_log: AutoconfigLog = AutoconfigLog()
        autoconfig_log.session_id = session_id
        autoconfig_log.instance_id = self._get_instance_id()
        autoconfig_log.msg = msg
        try:
            autoconfig_log.level = int(level)
        except TypeError:
            autoconfig_log.level = 0
            logger.warning('Unable to parse level for autoconfig log')
        self._save(autoconfig_log)
        autoconf: Optional[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_by_session_id(self._session, self._get_instance_id(), session_id)
        if int(level) == 4 and autoconf is not None and autoconf.status == 1:
            autoconf.status = 3
            self._save(autoconf)
        # TODO Commit?

    async def autoconfig_status(self) -> web.Response:
        body = await self.request.json()
        session_id: Optional[int] = body.get('session_id', None)
        update_data = {
            'ip': self._get_request_address()
        }
        where = {
            'session_id': session_id,
            'instance_id': self._get_instance_id()
        }
        await AutoconfigRegistrationHelper.update_ip(self._session, self._get_instance_id(), session_id,
                                                     self._get_request_address())
        return web.Response(text="", status=200)

    async def _add_to_queue(self, data):
        await self._get_data_queue().put(data)

    def _check_mitm_status_auth(self):
        """
        Checks for /status/ authorization. Raises web.HTTPUnauthorized if access is denied
        Returns:

        """
        auth = self.request.headers.get('Authorization')
        if self._get_mad_args().mitm_status_password != "" and \
                (not auth or auth != self._get_mad_args().mitm_status_password):
            raise web.HTTPUnauthorized

    async def _check_mitm_device_auth(self):
        """
        Checks whether the credentials passed are valid compared to those last read by MappingManager
        Returns:

        """
        auth = self._request.headers.get('Authorization')
        if not check_auth(logger, auth, self._get_mad_args(), await (self._get_mapping_manager().get_auths())):
            logger.warning("Unauthorized attempt to connect from {}", self._get_request_address())
            raise web.HTTPUnauthorized

    async def _check_origin_header(self):
        """
        Checks whether an origin-header was passed and whether the given origin is allowed to access this instance
        Returns:

        """
        origin = self._request.headers.get('Origin')
        if origin is None:
            logger.warning("Missing Origin header in request")
            raise web.HTTPUnauthorized
        elif (await self._get_mapping_manager().get_all_devicemappings()).keys() is not None and \
                origin not in (await self._get_mapping_manager().get_all_devicemappings()).keys():
            logger.warning("MITMReceiver request without Origin or disallowed Origin")
            raise web.HTTPUnauthorized
