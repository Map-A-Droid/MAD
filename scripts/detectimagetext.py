import pytesseract
from pytesseract import Output
import cv2
img = cv2.imread('screenshot_tv2.jpg')

d = pytesseract.image_to_data(img, output_type=Output.DICT)

n_boxes = len(d['level'])
for i in range(n_boxes):
    if '@gmail.com' in (d['text'][i]):
        (x, y, w, h) = (d['left'][i], d['top'][i], d['width'][i], d['height'][i])
        click_x, click_y = x + w / 2, y + h /2
        print (click_x,click_y)
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

cv2.imshow('img', img)
cv2.waitKey(0)