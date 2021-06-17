from functools import wraps
from typing import Optional, Tuple, Dict, Any

from mapadroid.db.helper.AutoconfigLogsHelper import AutoconfigLogsHelper
from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.model import AutoconfigRegistration
from aiohttp import web
from loguru import logger

from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from mapadroid.utils.PDConfig import PDConfig
from mapadroid.utils.RGCConfig import RGCConfig


def validate_session(func) -> Any:
    @wraps(func)
    async def decorated(self: AutoconfStatusOperationEndpoint, *args, **kwargs):
        try:
            body = await self.request.json()
            session_id: Optional[int] = body.get('session_id', None)
            session_id = int(session_id)
            autoconfig_registration: Optional[AutoconfigRegistration] = await AutoconfigRegistrationHelper\
                .get_by_session_id(self._session, self._get_instance_id(), session_id)

            if not autoconfig_registration:
                raise web.HTTPNotFound
            return func(self, *args, **kwargs)
        except (TypeError, ValueError):
            raise web.HTTPNotFound

    return decorated


class AutoconfStatusOperationEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/autoconfig/<int:session_id>/<string:operation"
    """

    async def preprocess(self) -> Tuple[Dict, str]:
        body = await self.request.json()
        operation: Optional[str] = body.get('operation', None)
        session_id: Optional[int] = body.get('session_id', None)
        if operation is None:
            raise web.HTTPNotFound
        log_data = {
            'session_id': session_id,
            'instance_id': self._get_instance_id(),
            'level': 2
        }
        return log_data, operation

    async def get(self):
        log_data, operation = self.preprocess()
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
        raise web.HTTPNotFound

    # TODO: Auth/preprocessing for autoconfig?
    async def post(self):
        log_data, operation = self.preprocess()
        if operation == 'log':
            return await self.autoconfig_log()
        raise web.HTTPNotFound

    async def delete(self):
        log_data, operation = self.preprocess()
        if operation == 'complete':
            if log_data:
                log_data['msg'] = 'Device ihas requested the completion of the auto-configuration session'
                await self.autoconfig_log(**log_data)
            return await self._autoconfig_complete()
        raise web.HTTPNotFound

    @validate_session
    async def _autoconfig_get_config(self):
        body = await self.request.json()
        session_id: Optional[int] = body.get('session_id', None)
        operation: Optional[str] = body.get('operation', None)
        try:
            sql = "SELECT sd.`name`\n" \
                  "FROM `settings_device` sd\n" \
                  "INNER JOIN `autoconfig_registration` ar ON ar.`device_id` = sd.`device_id`\n" \
                  "WHERE ar.`session_id` = %s AND ar.`instance_id` = %s"
            origin = await self._db_wrapper.autofetch_value_async(sql, (session_id, self._get_instance_id()))
            if operation in ['pd', 'rgc']:
                if operation == 'pd':
                    config = PDConfig(self._session, self._get_instance_id(), self._get_mad_args())
                else:
                    config = RGCConfig(self._session, self._get_instance_id(), self._get_mad_args())
                # TODO: Fix return type of generate_config/stream it properly
                return web.FileResponse(await config.generate_config(origin),
                                        headers={'Content-Disposition': f"Attachment; filename=conf.xml"})
            elif operation in ['google']:
                sql = "SELECT ag.`username`, ag.`password`\n" \
                      "FROM `settings_pogoauth` ag\n" \
                      "INNER JOIN `autoconfig_registration` ar ON ar.`device_id` = ag.`device_id`\n" \
                      "WHERE ar.`session_id` = %s and ag.`instance_id` = %s and ag.`login_type` = %s"
                login = await self._db_wrapper.autofetch_row_async(sql, (
                    session_id, self._db_wrapper.__instance_id, 'google'))
                if login:
                    return web.Response(status=200, text='\n'.join([login['username'], login['password']]))
                else:
                    raise web.HTTPNotFound
            elif operation == 'origin':
                return web.Response(status=200, text=origin)
        except Exception:
            logger.opt(exception=True).critical('Unable to process autoconfig')
            raise web.HTTPNotAcceptable

    @validate_session
    async def _autoconfig_complete(self):
        body = await self.request.json()
        session_id: Optional[int] = body.get('session_id', None)
        try:
            info = {
                'session_id': session_id,
                'instance_id': self._get_instance_id()
            }

            max_msg_level: Optional[int] = await AutoconfigLogsHelper\
                .get_max_level_of_session(self._session, self._get_instance_id(), session_id)
            if max_msg_level and max_msg_level == 4:
                logger.warning('Unable to clear session due to a failure.  Manual deletion required')
                update_data = {
                    'status': 4
                }
                where = {
                    'session_id': session_id,
                    'instance_id': self._get_instance_id()
                }
                await self._db_wrapper.autoexec_update('autoconfig_registration', update_data, where_keyvals=where)
                raise web.HTTPBadRequest
            await self._db_wrapper.autoexec_delete('autoconfig_registration', info)
            return web.Response(status=200, text="")
        except Exception:
            logger.opt(exception=True).error('Unable to delete session')
            raise web.HTTPNotFound
