import datetime
import os
import time

from PIL import Image

import mapadroid

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
