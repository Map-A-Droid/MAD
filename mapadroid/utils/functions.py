import calendar
import datetime
import os
import time

from PIL import Image

import mapadroid

with open(os.path.join(mapadroid.MAD_ROOT, 'static/madmin/templates/phone.tpl'), 'r') as file:
    phone_template = file.read().replace('\n', '')


def generate_mappingjson(mappings_path):
    import json
    newfile = {}
    newfile['areas'] = {"entries": {}, "index": 0}
    newfile['auth'] = {"entries": {}, "index": 0}
    newfile['devices'] = {"entries": {}, "index": 0}
    newfile['walker'] = {"entries": {}, "index": 0}
    newfile['devicesettings'] = {"entries": {}, "index": 0}
    newfile['monivlist'] = {"entries": {}, "index": 0}
    newfile['walkerarea'] = {"entries": {}, "index": 0}
    newfile['migrated'] = True

    with open(mappings_path, 'w') as outfile:
        json.dump(newfile, outfile, indent=4, sort_keys=True)


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


def get_min_period():
    min = datetime.datetime.utcnow().strftime("%M")
    if 0 <= int(min) < 10:
        pos = 0
    elif 10 <= int(min) < 20:
        pos = 10
    elif 20 <= int(min) < 30:
        pos = 20
    elif 30 <= int(min) < 40:
        pos = 30
    elif 40 <= int(min) < 50:
        pos = 40
    elif 50 <= int(min) < 60:
        pos = 50

    returndatetime = datetime.datetime.utcnow().replace(
        minute=int(pos), second=0, microsecond=0)
    return calendar.timegm(returndatetime.utctimetuple())


def get_now_timestamp():
    return datetime.datetime.now().timestamp()


def ConvertDateTimeToLocal(timestampValue):
    offset = datetime.datetime.now() - datetime.datetime.utcnow()
    return datetime.datetime.fromtimestamp(timestampValue) + offset + datetime.timedelta(seconds=1)
