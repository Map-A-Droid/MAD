import glob
import logging
import os

import cv2
import imutils
import numpy as np

log = logging.getLogger(__name__)

weatherImages = {
    'weatherIcon_small_sunny.png': 1,
    'weatherIcon_small_rain.png': 2,
    'weatherIcon_small_partlycloudy_day.png': 3,
    'weatherIcon_small_cloudy.png': 4,
    'weatherIcon_small_windy.png': 5,
    'weatherIcon_small_snow.png': 6,
    'weatherIcon_small_fog.png': 7,
    'weatherIcon_small_clear.png': 11,
    'weatherIcon_small_partlycloudy_night.png': 13,
    'weatherIcon_small_extreme.png': 16
}


def weather_image_matching(weather_icon_name, screenshot_name):

    weather_icon = cv2.imread(weather_icon_name, 3)

    if weather_icon is None:
        log.error('weather_image_matching: %s appears to be corrupted' %
                  str(url_img_name))
        return 0

    screenshot_img = cv2.imread(screenshot_name, 3)

    if screenshot_img is None:
        log.error('weather_image_matching: %s appears to be corrupted' %
                  str(screenshot_name))
        return 0
    height, width, _ = weather_icon.shape

    fort_img = imutils.resize(
        screenshot_img, width=int(screenshot_img.shape[1] * 2))
    height_f, width_f, _ = screenshot_img.shape
    screenshot_img = screenshot_img[0:int(height_f/7), 0:width_f]

    resized = imutils.resize(
        weather_icon, width=int(weather_icon.shape[1] * 1))

    crop = cv2.Canny(resized, 100, 200)

    if crop.mean() == 255 or crop.mean() == 0:
        return 0

    (tH, tW) = crop.shape[:2]

    screenshot_img = cv2.blur(screenshot_img, (3, 3))
    screenshot_img = cv2.Canny(screenshot_img, 50, 100)

    found = None
    for scale in np.linspace(0.2, 1, 5)[::-1]:
        resized = imutils.resize(screenshot_img, width=int(
            screenshot_img.shape[1] * scale))
        r = screenshot_img.shape[1] / float(resized.shape[1])

        if resized.shape[0] < tH or resized.shape[1] < tW:
            break

        result = cv2.matchTemplate(resized, crop, cv2.TM_CCOEFF_NORMED)
        (_, maxVal, _, maxLoc) = cv2.minMaxLoc(result)

        (endX, endY) = (int((maxLoc[0] + tW) * r), int((maxLoc[1] + tH) * r))

        if endY > height_f/7 and endX < width_f/2:
            maxVal = 0

        if found is None or maxVal > found[0]:
            found = (maxVal, maxLoc, r)

    return found[0]


def checkWeather(raidpic):
    foundweather = None

    for file in glob.glob(os.path.join('ocr', 'weather', 'weatherIcon_small_*.png')):
        filename = os.path.basename(file)
        find_weather = weather_image_matching(file, raidpic)

        if foundweather is None or find_weather > foundweather[0]:
            foundweather = find_weather, os.path.basename(file)

    if foundweather[0] > 0:
        weatherName = foundweather[1].split('.')
        log.info('The weather on the screenshot could be identified  (%s)' %
                 str(weatherName[0].replace('_', ' ')))
        return True, weatherImages[os.path.basename(foundweather[1])]
        # True, WeatherID
        # send to database !
    else:
        log.error('The weather on the screenshot could not be identified')
        return False, False
        # nothing to do
