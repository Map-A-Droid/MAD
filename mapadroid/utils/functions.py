import datetime
import json
import os
import time

import requests
from cachetools.func import ttl_cache
from PIL import Image

import mapadroid
from mapadroid.utils.global_variables import VERSIONCODES_URL
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.system)


with open(os.path.join(mapadroid.MAD_ROOT, 'static/madmin/templates/phone.tpl'), 'r') as file:
    phone_template = file.read().replace('\n', '')


def creation_date(path_to_file):
    return os.path.getmtime(path_to_file)


def generate_path(path):
    return os.path.join(os.path.join(mapadroid.MAD_ROOT, path))


def image_resize(image, savepath, width=None, height=None):
    basewidth = width
    filename = os.path.basename(image)
    with Image.open(image) as img:
        wpercent = (basewidth / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        img = img.resize((basewidth, hsize), Image.ANTIALIAS)
        pre, _ = os.path.splitext(filename)
        img.save(os.path.join(savepath, str(pre) + '.jpg'))

    return True


def pngtojpg(image):
    pre, _ = os.path.splitext(image)
    with Image.open(image) as im:
        rgb_im = im.convert('RGB')
        rgb_im.save(pre + '.jpg')
    return True


def generate_phones(phonename, add_text, adb_option, screen, filename, datetimeformat, dummy=False):
    if not dummy:
        creationdate = datetime.datetime.fromtimestamp(
            creation_date(filename)).strftime(datetimeformat)
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


@ttl_cache
def get_version_codes(force_gh=False):
    if not force_gh:
        try:
            with open('configs/version_codes.json') as fh:
                return json.load(fh)
        except (IOError, json.decoder.JSONDecodeError):
            pass
    try:
        raw_resp = requests.get(VERSIONCODES_URL)
        raw_resp.raise_for_status()
    except Exception:
        logger.error("Unable to query GitHub")
        return {}
    else:
        try:
            return raw_resp.json()
        except json.decoder.JSONDecodeError:
            logger.exception("Unable to parse the JSON when getting version codes")
            return {}
