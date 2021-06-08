import copy
import json
from io import BytesIO
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Union
from xml.sax.saxutils import escape

from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.helper.AutoconfigFileHelper import AutoconfigFileHelper
from mapadroid.db.helper.OriginHopperHelper import OriginHopperHelper
from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.helper.SettingsDevicepoolHelper import \
    SettingsDevicepoolHelper
from mapadroid.db.helper.SettingsWalkerHelper import SettingsWalkerHelper
from mapadroid.db.model import (AutoconfigFile, OriginHopper, SettingsAuth,
                                SettingsDevice, SettingsDevicepool,
                                SettingsWalker)

USER_READABLE_ERRORS = {
    str: 'string (MapADroid)',
    int: 'Integer (1,2,3)',
    float: 'Decimal (1.0, 1.5)',
    list: 'Comma-delimited list',
    bool: 'True|False'
}


async def validate_hopper_ready(session: AsyncSession, instance_id: int) -> bool:
    walkers: List[SettingsWalker] = await SettingsWalkerHelper.get_all(session, instance_id)
    return len(walkers) > 0


# TODO: Singleton for the instance ID?
async def origin_generator(session: AsyncSession,
                           instance_id: int, *args, **kwargs) -> Union[SettingsDevice, web.Response]:
    origin = kwargs.get('OriginBase', None)
    walker_id = kwargs.get('walker', None)
    if walker_id is not None:
        try:
            walker_id: int = int(walker_id)
        except ValueError:
            return web.Response(status=404, text='"walker" value must be an integer')
    pool_id = kwargs.get('pool', None)
    if pool_id is not None:
        try:
            pool_id: int = int(pool_id)
        except ValueError:
            return web.Response(status=404, text='"pool" value must be an integer')
    is_ready = validate_hopper_ready(session, instance_id)
    if not is_ready:
        return web.Response(status=404, text='Unable to verify hopper. Likely no walkers have been configured at all.')
    if origin is None:
        return web.Response(status=400, text='Please specify an Origin Prefix')
    walkers: List[SettingsWalker] = await SettingsWalkerHelper.get_all(session, instance_id)
    walker: Optional[SettingsWalker] = None
    if walker_id is not None:
        for possible_walker in walkers:
            if possible_walker.walker_id == walker_id:
                walker = possible_walker
                break
        if walker is None:
            return web.Response(status=404, text='Walker ID not found')
    else:
        walker = walkers[0]
    if pool_id is not None:
        pool: Optional[SettingsDevicepool] = await SettingsDevicepoolHelper.get(session, pool_id)
        if pool is None:
            return web.Response(status=404, text='Devicepool not found')
    origin_hopper: Optional[OriginHopper] = await OriginHopperHelper.get(session, origin)
    if not origin_hopper:
        origin_hopper = OriginHopper()
        origin_hopper.origin = origin
    next_id = origin_hopper.last_id + 1 if origin_hopper is not None else 0
    origin_hopper.last_id = next_id
    session.add(origin_hopper)

    origin = '%s%03d' % (origin, next_id,)
    device: SettingsDevice = SettingsDevice()
    device.pool_id = pool_id
    device.walker_id = walker.walker_id
    device.name = origin
    session.add(device)
    return device


class AutoConfIssue(Exception):
    def __init__(self, issues):
        super().__init__()
        self.issues = issues


class AutoConfigCreator:
    origin_field: str = None
    source: str = None
    sections: Dict = {}
    host_field: str = None

    def __init__(self, session: AsyncSession, instance_id: int, args):
        self._args = args
        self.contents: Dict[str, Any] = {}
        self.configured: bool = False
        self._session: AsyncSession = session
        self._instance_id: int = instance_id
        # TODO: Load config -> factory method to be awaited for...
        self.load_config()

    async def delete(self, session: AsyncSession):
        config: Optional[AutoconfigFile] = await AutoconfigFileHelper.get(session, self._instance_id, self.source)
        if config is not None:
            await session.delete(config)

    async def generate_config(self, origin: str) -> BytesIO:
        origin_config = await self.get_config()
        origin_config[self.origin_field] = origin
        conv_xml = ["<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\" ?>", "<map>"]
        for _, sect_conf in self.sections.items():
            for key, elem in sect_conf.items():
                if key not in origin_config:
                    continue
                elem_type = "string"
                value = escape(str(origin_config[key]))
                if elem['expected'] == bool:
                    elem_type = "boolean"
                xml_elem = "<{} name=\"{}\"".format(elem_type, key)
                if elem['expected'] == bool:
                    xml_elem += " value=\"{}\" />".format(value)
                else:
                    xml_elem += ">{}</{}>".format(value, elem_type)
                conv_xml.append('    {}'.format(xml_elem))
        conv_xml.append('</map>')
        # TODO: Threaded exec needed?
        return BytesIO('\n'.join(conv_xml).encode('utf-8'))

    async def get_config(self) -> dict:
        tmp_config: dict = copy.copy(self.contents)
        auth: Optional[SettingsAuth] = None
        try:
            auth: Optional[SettingsAuth] = await SettingsAuthHelper.get(self._session, self._instance_id,
                                                                        tmp_config['mad_auth'])
            del tmp_config['mad_auth']
        except KeyError:
            auth = None
        if auth is not None:
            tmp_config['auth_username'] = auth.username
            tmp_config['auth_password'] = auth.password
            tmp_config['switch_enable_auth_header'] = True
        else:
            tmp_config['switch_enable_auth_header'] = False
            tmp_config['auth_username'] = ""
            tmp_config['auth_password'] = ""
        return tmp_config

    async def load_config(self) -> NoReturn:
        try:
            config: Optional[AutoconfigFile] = await AutoconfigFileHelper.get(self._session, self._instance_id,
                                                                              self.source)
            if config is not None:
                self.contents = json.loads(config.data)
                self.configured = True
            else:
                self.contents = {}
        except json.decoder.JSONDecodeError:
            self.contents = {}
        for _, sect_conf in self.sections.items():
            for key, elem in sect_conf.items():
                if key not in self.contents:
                    self.contents[key] = elem['default']
                    continue

    async def save_config(self, user_vals: dict) -> NoReturn:
        self.validate(user_vals)
        await AutoconfigFileHelper.insert_or_update(self._session, self._instance_id, self.source,
                                                    json.dumps(self.contents))

    def validate(self, user_vals: dict) -> bool:
        processed = []
        missing: List[str] = []
        invalid: List[Tuple[str, str]] = []
        for sect_conf in self.sections.values():
            for key, elem in sect_conf.items():
                processed.append(key)
                if elem['required'] and key not in user_vals:
                    if key not in self.contents:
                        missing.append(key)
                    continue
                if elem['required'] and user_vals[key] in [None, ""]:
                    if key not in self.contents:
                        missing.append(key)
                        continue
                check_func = ""
                try:
                    check_func = elem['expected']
                    if elem['expected'] == 'bool':
                        if user_vals[key] not in [True, False]:
                            invalid.append((key, USER_READABLE_ERRORS[bool]))
                    self.contents[key] = check_func(user_vals[key])
                except KeyError:
                    if key not in self.contents:
                        self.contents[key] = elem['default'] if elem['default'] not in ['None', None] else ""
                except (TypeError, ValueError):
                    invalid.append((key, USER_READABLE_ERRORS[check_func]))
        unknown = set(list(user_vals.keys())) - set(processed)
        try:
            invalid_dest = ['127.0.0.1', '0.0.0.0']
            for dest in invalid_dest:
                if dest in self.contents[self.host_field]:
                    invalid.append((self.host_field, "Routable address from outside the server"))
        except KeyError:
            pass
        issues = {}
        if missing:
            issues['missing'] = missing
        if invalid:
            issues['invalid'] = invalid
        if unknown:
            issues['unknown'] = unknown
        if issues:
            raise AutoConfIssue(issues)
        return True
