import asyncio
import concurrent
import datetime
import json
import os
import time

from PIL import Image
from aiocache import cached
from aiofile import async_open

import mapadroid
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.RestHelper import RestHelper, RestApiResult
from mapadroid.utils.global_variables import VERSIONCODES_URL

with open(os.path.join(mapadroid.MAD_ROOT, 'static/madmin/templates/phone.tpl'), 'r') as file:
    phone_template = file.read().replace('\n', '')


def creation_date(path_to_file) -> int:
    return int(os.path.getmtime(path_to_file))


def generate_path(path):
    return os.path.join(os.path.join(mapadroid.MAD_ROOT, path))


async def image_resize(image, savepath, width=None, height=None):
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(
            pool, _process_image_resize, image, savepath, width)


def _process_image_resize(image, savepath, width):
    basewidth = width
    filename = os.path.basename(image)
    with Image.open(image) as img:
        wpercent = (basewidth / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        img = img.resize((basewidth, hsize), Image.ANTIALIAS)
        pre, _ = os.path.splitext(filename)
        img.save(os.path.join(savepath, str(pre) + '.jpg'))


async def pngtojpg(image):
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(
            pool, process_png_to_jpg, image)


def process_png_to_jpg(image):
    pre, _ = os.path.splitext(image)
    with Image.open(image) as im:
        rgb_im = im.convert('RGB')
        rgb_im.save(pre + '.jpg')


def generate_phones(phonename, add_text, adb_option, screen, filename, datetimeformat, dummy=False):
    if not dummy:
        creationdate = str(creation_date(filename))
        #date = DatetimeWrapper.fromtimestamp(last_modification_timestamp)
        #creationdate = date.strftime(datetimeformat)
    else:
        creationdate = 'No Screen available'

    return (
        phone_template.replace('<<phonename>>', phonename)
            .replace('<<adb_option>>', str(adb_option))
            .replace('<<add_text>>', add_text)
            .replace('<<screen>>', screen)
            .replace('<<creationdate>>', creationdate)
            .replace('<<time>>', str(int(time.time())))
    )


@cached(ttl=10 * 60)
async def get_version_codes(force_gh=False):
    if not force_gh:
        try:
            async with async_open('configs/version_codes.json', "r") as fh:
                return json.load(await fh.read())
        except (IOError, json.decoder.JSONDecodeError):
            pass
    result: RestApiResult = await RestHelper.send_get(VERSIONCODES_URL)
    if result.status_code == 200:
        return result.result_body
    else:
        return {}
