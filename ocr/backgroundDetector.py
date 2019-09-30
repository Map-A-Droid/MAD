import cv2
from collections import Counter
from bitstring import xrange


class ColorAnalyser(object):
    def __init__(self, logger):
        self.img = ""
        self._logger = logger

        self.manual_count = {}
        self.w, self.h, self.channels = 0, 0, 0
        self.total_pixels = 0
        self.percentage_of_first = 0

    def count(self):
        for y in xrange(0, self.h):
            for x in xrange(0, self.w):
                RGB = (self.img[x, y, 2], self.img[x, y, 1], self.img[x, y, 0])
                if RGB in self.manual_count:
                    self.manual_count[RGB] += 1
                else:
                    self.manual_count[RGB] = 1

    def detect(self, image):
        self.img = image
        self.w, self.h, self.channels = self.img.shape
        self.total_pixels = self.w * self.h
        self.count()
        self.number_counter = Counter(self.manual_count).most_common(20)
        self._logger.debug("Detected Colors: {}".format(str(self.number_counter)))
        self.percentage_of_first = (float(self.number_counter[0][1]) / self.total_pixels)
        self._logger.debug("Detected most color percent value: {}".format(str(self.percentage_of_first)))
        self.manual_count = {}
        if self.percentage_of_first > 0.85:
            returning_color = self.number_counter[0][0]
            self.number_counter = ""
            return returning_color
        else:
            return None
