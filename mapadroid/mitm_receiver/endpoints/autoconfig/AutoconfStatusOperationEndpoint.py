from __future__ import annotations

from functools import wraps
from typing import Optional, Tuple, Dict, Any

from aiohttp import web
from loguru import logger

from mapadroid.db.helper.AutoconfigLogsHelper import AutoconfigLogsHelper
from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.model import AutoconfigRegistration, SettingsDevice, SettingsPogoauth
from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from mapadroid.utils.PDConfig import PDConfig
from mapadroid.utils.RGCConfig import RGCConfig


def validate_session(func) -> Any:
    @wraps(func)
    async def decorated(self: AutoconfStatusOperationEndpoint, *args, **kwargs):
        try:
            session_id: int = self.request.match_info.get('session_id')
            session_id = int(session_id)
            autoconfig_registration: Optional[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
                .get_by_session_id(self._session, self._get_instance_id(), session_id)

            if not autoconfig_registration:
                raise web.HTTPNotFound()
            # elif autoconfig_registration.status != 1:
            #    raise web.HTTPConflict()
            return await func(self, *args, **kwargs)
        except (TypeError, ValueError):
            raise web.HTTPNotFound()

    return decorated


class AutoconfStatusOperationEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/autoconfig/<int:session_id>/<string:operation"
    """

    async def preprocess(self) -> Tuple[Dict, str]:
        operation: Optional[str] = self.request.match_info.get('operation')
        session_id: Optional[int] = self.request.match_info.get('session_id')
        if operation is None:
            raise web.HTTPNotFound()
        log_data = {
            'session_id': session_id,
            'instance_id': self._get_instance_id(),
            'level': 2
        }
        return log_data, operation

    async def get(self):
        log_data, operation = await self.preprocess()
        if operation == 'status':
            if log_data:
                log_data['msg'] = 'Device is checking status of the session'
                await self.autoconfig_log(**log_data)
            return await self.autoconfig_status()
        elif operation in ['pd', 'rgc', 'google', 'origin']:
            if log_data:
                log_data['msg'] = 'Device is attempting to pull a config endpoint, {}'.format(operation)
                await self.autoconfig_log(**log_data)
            return await self._autoconfig_get_config()
        raise web.HTTPNotFound()

    # TODO: Auth/preprocessing for autoconfig?
    async def post(self):
        log_data, operation = await self.preprocess()
        if operation == 'log':
            await self.autoconfig_log(**log_data)
            return web.Response(text="", status=201)
        raise web.HTTPNotFound()

    async def delete(self):
        log_data, operation = await self.preprocess()
        if operation == 'complete':
            if log_data:
                log_data['msg'] = 'Device ihas requested the completion of the auto-configuration session'
                await self.autoconfig_log(**log_data)
            return await self._autoconfig_complete()
        raise web.HTTPNotFound()

    @validate_session
    async def _autoconfig_get_config(self):
        session_id: int = self.request.match_info.get('session_id')
        operation: Optional[str] = self.request.match_info.get('operation')
        try:
            device_settings: Optional[SettingsDevice] = await SettingsDeviceHelper \
                .get_device_settings_with_autoconfig_registration_pending(self._session, self._get_instance_id(),
                                                                          session_id)
            if operation in ['pd', 'rgc']:
                if operation == 'pd':
                    config = PDConfig(self._session, self._get_instance_id(), self._get_mad_args())
                else:
                    config = RGCConfig(self._session, self._get_instance_id(), self._get_mad_args())
                await config.load_config()
                # TODO: Fix return type of generate_config/stream it properly
                config_bytes = await config.generate_config(device_settings.name)
                return web.Response(body=config_bytes,
                                    headers={'Content-Disposition': f"Attachment; filename=conf.xml"})
            elif operation in ['google']:
                login: Optional[SettingsPogoauth] = await SettingsPogoauthHelper \
                    .get_google_credentials_of_autoconfig_registered_device(self._session, self._get_instance_id(),
                                                                            session_id)
                if login:
                    return web.Response(status=200, text='\n'.join([login.username, login.password]))
                else:
                    raise web.HTTPNotFound
            elif operation == 'origin':
                return web.Response(status=200, text=device_settings.name)
        except Exception as e:
            logger.opt(exception=True).critical('Unable to process autoconfig')
            raise web.HTTPNotAcceptable()

    @validate_session
    async def _autoconfig_complete(self):
        session_id: int = self.request.match_info.get('session_id')
        try:
            max_msg_level: Optional[int] = await AutoconfigLogsHelper \
                .get_max_level_of_session(self._session, self._get_instance_id(), session_id)
            if max_msg_level and max_msg_level == 4:
                logger.warning('Unable to clear session due to a failure.  Manual deletion required')
                await AutoconfigRegistrationHelper.update_status(self._session, self._get_instance_id(), session_id,
                                                                 status=4)
                await self._session.commit()
                raise web.HTTPBadRequest()
            await AutoconfigRegistrationHelper.delete(self._session, self._get_instance_id(), session_id)
            self._commit_trigger = True
            return web.Response(status=200, text="")
        except Exception:
            logger.opt(exception=True).error('Unable to delete session')
            raise web.HTTPNotFound()
