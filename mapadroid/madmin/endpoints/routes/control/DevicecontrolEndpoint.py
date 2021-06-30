import os
from typing import List, Optional, Dict

import aiohttp_jinja2

import mapadroid
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import generate_device_screenshot_path
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry
from mapadroid.utils.functions import generate_phones, image_resize


class DevicecontrolEndpoint(AbstractControlEndpoint):
    """
    "/devicecontrol"
    """

    # TODO: Auth
    # TODO: Also "post"?
    # TODO: nocache?
    @aiohttp_jinja2.template('phonescreens.html')
    async def get(self):
        # TODO: Async exec?
        if not os.path.exists(os.path.join(mapadroid.MAD_ROOT, self._get_mad_args().temp_path, "madmin")):
            os.makedirs(os.path.join(self._get_mad_args().temp_path, "madmin"))

        screens_phone = []
        if self._get_ws_server() is not None:
            phones = await self._get_ws_server().get_reg_origins()
        else:
            phones = []
        devicemappings: Optional[
            Dict[str, DeviceMappingsEntry]] = await self._get_mapping_manager().get_all_devicemappings()

        # Sort devices by name.
        phones = sorted(phones)
        ws_connected_phones: List[str] = []
        for phonename in phones:
            ws_connected_phones.append(phonename)
            add_text = ""
            adb_option = False
            device_entry: Optional[DeviceMappingsEntry] = devicemappings.get(phonename)
            # TODO: origin_logger = get_origin_logger(self._logger, origin=phonename)
            # TODO: Adb stuff needs to run async
            if device_entry and device_entry.device_settings.adbname is not None \
                    and self._adb_connect.check_adb_status(device_entry.device_settings.adbname) is not None:
                # This append is odd
                # ws_connected_phones.append(adb)
                adb_option = True
                add_text = '<b>ADB</b>'
            else:
                # ws_connected_phones.append(adb)
                pass

            filename = generate_device_screenshot_path(phonename, device_entry, self._get_mad_args())
            try:
                screenshot_ending: str = ".jpg"
                # TODO: Async
                await image_resize(filename, os.path.join(
                    self._get_mad_args().temp_path, "madmin"), width=250)
                screen = "screenshot/screenshot_" + str(phonename) + screenshot_ending + "?madmin=1"
                screens_phone.append(
                    generate_phones(phonename, add_text, adb_option,
                                    screen, filename, self._datetimeformat, dummy=False)
                )
            except IOError:
                screen = "static/dummy.png"
                screens_phone.append(generate_phones(
                    phonename, add_text, adb_option, screen, filename, self._datetimeformat, dummy=True))
                try:
                    os.remove(filename)
                    # origin_logger.info("Screenshot {} was corrupted and has been deleted", filename)
                except OSError:
                    pass

        for phonename in self._adb_connect.return_adb_devices():
            if phonename.serial not in ws_connected_phones:
                for device_name, entry in devicemappings.items():
                    if phonename.serial == entry.device_settings.adbname:
                        adb_option = True
                        add_text = '<b>ADB - no WS <i class="fa fa-exclamation-triangle"></i></b>'
                        filename = generate_device_screenshot_path(device_name, entry, self._get_mad_args())
                        if os.path.isfile(filename):
                            await image_resize(filename,
                                               os.path.join(mapadroid.MAD_ROOT, self._get_mad_args().temp_path,
                                                            "madmin"),
                                               width=250)
                            screenshot_ending: str = ".jpg"
                            screen = "screenshot/screenshot_" + str(device_name) + screenshot_ending + "?madmin=1"
                            screens_phone.append(generate_phones(device_name, add_text, adb_option, screen, filename,
                                                                 self._datetimeformat, dummy=False))
                        else:
                            screen = "static/dummy.png"
                            screens_phone.append(generate_phones(device_name, add_text, adb_option, screen, filename,
                                                                 self._datetimeformat, dummy=True))
        return {
            "editform": screens_phone,
            "header": "Device control",
            "title": "Device control"
        }
