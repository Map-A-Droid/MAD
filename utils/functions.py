import datetime
import os
import platform
import calendar

import cv2

with open('madmin/static/vars/template/phone.tpl', 'r') as file:
    phone_template = file.read().replace('\n', '')


def creation_date(path_to_file):
    return os.path.getctime(path_to_file)


def generate_path(path):
    return os.path.join(os.path.join(os.path.dirname(__file__), os.pardir, path))


def image_resize(image, savepath, width=None, height=None, inter=cv2.INTER_AREA):
    # initialize the dimensions of the image to be resized and
    # grab the image size
    filename = os.path.basename(image)
    image = cv2.imread(image, 3)
    (h, w) = image.shape[:2]

    # if both the width and height are None, then return the
    # original image
    if width is None and height is None:
        return image

    # check to see if the width is None
    if width is None:
        # calculate the ratio of the height and construct the
        # dimensions
        r = height / float(h)
        dim = (int(w * r), height)

    # otherwise, the height is None
    else:
        # calculate the ratio of the width and construct the
        # dimensions
        r = width / float(w)
        dim = (width, int(h * r))

    # resize the image
    resized = cv2.resize(image, dim, interpolation=inter)
    pre, _ = os.path.splitext(filename)
    cv2.imwrite(os.path.join(savepath, str(pre) + '.png'),
                resized, [int(cv2.IMWRITE_PNG_COMPRESSION), 9])

    # return the resized image
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


