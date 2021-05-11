import os
from typing import List

import aiohttp_jinja2

import mapadroid
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import generate_device_screenshot_path
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
            phones = self._get_ws_server().get_reg_origins()
        else:
            phones = []
        devicemappings = await self._get_mapping_manager().get_all_devicemappings()

        # Sort devices by name.
        phones = sorted(phones)
        ws_connected_phones: List[str] = []
        for phonename in phones:
            ws_connected_phones.append(phonename)
            add_text = ""
            adb_option = False
            adb = devicemappings.get(phonename, {}).get('adb', False)
            # TODO: origin_logger = get_origin_logger(self._logger, origin=phonename)
            # TODO: Adb stuff needs to run async
            if adb is not None and self._adb_connect.check_adb_status(adb) is not None:
                # This append is odd
                # ws_connected_phones.append(adb)
                adb_option = True
                add_text = '<b>ADB</b>'
            else:
                # ws_connected_phones.append(adb)
                pass

            filename = generate_device_screenshot_path(phonename, devicemappings, self._get_mad_args())
            try:
                screenshot_ending: str = ".jpg"
                # TODO: Async
                image_resize(filename, os.path.join(
                    self._get_mad_args().temp_path, "madmin"), width=250)
                screen = "screenshot/madmin/screenshot_" + str(phonename) + screenshot_ending
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
                devicemappings = await self._get_mapping_manager().get_all_devicemappings()
                for pho in devicemappings:
                    if phonename.serial == devicemappings[pho].get('adb', False):
                        adb_option = True
                        add_text = '<b>ADB - no WS <i class="fa fa-exclamation-triangle"></i></b>'
                        filename = generate_device_screenshot_path(pho, devicemappings, self._get_mad_args())
                        if os.path.isfile(filename):
                            image_resize(filename, os.path.join(mapadroid.MAD_ROOT, self._get_mad_args().temp_path,
                                                                "madmin"),
                                         width=250)
                            screenshot_ending: str = ".jpg"
                            screen = "screenshot/madmin/screenshot_" + str(pho) + screenshot_ending
                            screens_phone.append(generate_phones(pho, add_text, adb_option, screen, filename,
                                                                 self._datetimeformat, dummy=False))
                        else:
                            screen = "static/dummy.png"
                            screens_phone.append(generate_phones(pho, add_text, adb_option, screen, filename,
                                                                 self._datetimeformat, dummy=True))
        return {
            "editform": screens_phone,
            "header": "Device control",
            "title": "Device control"
        }
