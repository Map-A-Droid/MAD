import argparse
import sys
sys.path.append("..")
from utils.resolution import Resocalculator
import cv2
import sys
import numpy as np
import pytesseract
import os
from PIL import Image

class testimage(object):
    def __init__(self, image, mode):
        
        self._image = cv2.imread(image)
        self._screen_y, self._screen_x, _ = self._image.shape
        self._mode = mode
        print (float(self._screen_y) / float(self._screen_x))

        self._resocalc = Resocalculator
        print (self._resocalc.get_x_y_ratio(self, self._screen_x, self._screen_y))
        
        if self._mode == "menu":
            self._image_check = self.check_menu(self._image)
            
        if self._mode == "open_del_item":
            self._image_check = self.open_del_item(self._image)
            
        if self._mode == "open_next_del_item":
            self._image_check = self.open_next_del_item(self._image)
        
        if self._mode == "swipe_del_item":
            self._image_check = self.swipe_del_item(self._image)
            
        if self._mode == "confirm_delete_item":
            self._image_check = self.confirm_delete_item(self._image)
            
        if self._mode == "open_del_quest":
            self._image_check = self.open_del_quest(self._image)
            
        if self._mode == "confirm_del_quest":
            self._image_check = self.confirm_del_quest(self._image)
            
        if self._mode == "open_gym":
            self._image_check = self.get_gym_click_coords(self._image)
            
        if self._mode == "find_pokeball":
            self._image_check = self.find_pokeball(self._image)
            sys.exit(0)

        if self._mode == "check_mainscreen":
            self._image_check = self.check_mainscreen(self._image)
            sys.exit(0)

        if self._mode == "read_item_text":
            self._image_check = self.get_delete_item_text(self._image)

        cv2.imshow("output", self._image_check)
        cv2.waitKey(0)
    
    def check_menu(self, image):
        print ('Check PokemonGo Menu')
        x, y = self._resocalc.get_item_menu_coords(self)[0], self._resocalc.get_item_menu_coords(self)[1]
        return cv2.circle(image,(int(x),int(y)), 20, (0,0,255), -1)
        
    def open_del_item(self, image):
        print ('Check Open del Item')
        x, y = self._resocalc.get_delete_item_coords(self)[0], self._resocalc.get_delete_item_coords(self)[1]
        return cv2.circle(image,(int(x),int(y)), 20, (0,0,255), -1)
        
    def open_next_del_item(self, image):
        print ('Check Open next del Item')
        x, y = self._resocalc.get_delete_item_coords(self)[0], self._resocalc.get_delete_item_coords(self)[1]
        y += self._resocalc.get_next_item_coord(self)
        return cv2.circle(image,(int(x),int(y)), 20, (0,0,255), -1)
        
    def swipe_del_item(self, image):
        print ('Swipe del item')
        x1, x2, y = self._resocalc.get_swipe_item_amount(self)[0], self._resocalc.get_swipe_item_amount(self)[1], self._resocalc.get_swipe_item_amount(self)[2]
        return cv2.line(image,(int(x1),int(y)),(int(x2),int(y)),(255,0,0),5)
        
    def confirm_delete_item(self, image):
        print ('Check confirm delete item')
        x, y = self._resocalc.get_confirm_delete_item_coords(self)[0], self._resocalc.get_confirm_delete_item_coords(self)[1]
        return cv2.circle(image,(int(x),int(y)), 20, (0,0,255), -1)
        
    def open_del_quest(self, image):
        print ('Check Open del quest')
        x, y = self._resocalc.get_delete_quest_coords(self)[0], self._resocalc.get_delete_quest_coords(self)[1]
        return cv2.circle(image,(int(x),int(y)), 20, (0,0,255), -1)
        
    def confirm_del_quest(self, image):
        print ('Check confirm delete quest')
        x, y = self._resocalc.get_confirm_delete_quest_coords(self)[0], self._resocalc.get_confirm_delete_quest_coords(self)[1]
        return cv2.circle(image,(int(x),int(y)), 20, (0,0,255), -1)
        
    def get_gym_click_coords(self, image):
        print ('Opening gym')
        x, y = self._resocalc.get_gym_click_coords(self)[0], self._resocalc.get_gym_click_coords(self)[1]
        return cv2.circle(image,(int(x),int(y)), 20, (0,0,255), -1)
        
    def find_pokeball(self, image):
        print ('Check Pokeball Mainscreen')
        height, width, _ = image.shape
        image = image[int(height) - int(round(height / 4.5)):int(height),
                             0: round(int(width) /2)]
        output = image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        radMin = int((width /  float(7.5)- 3) / 2)
        radMax = int((width / float(6.5) + 3) / 2)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.Canny(gray, 100, 50, apertureSize=3)   
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT,1,width / 8,param1=100,param2=15,minRadius=radMin,maxRadius=radMax)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                raidhash = output[y-r-1:y+r+1, x-r-1:x+r+1]
                cv2.imshow("output", np.hstack([raidhash]))
                cv2.waitKey(0)
        else:
            print ('No Mainscreen found')

    def get_delete_item_text(self, image):
        print ('Get item Text')
        x1, x2, y1, y2 = self._resocalc.get_delete_item_text(self)
        #y1 += self._resocalc.get_next_item_coord(self)
        #y2 += self._resocalc.get_next_item_coord(self)
        #y1 += self._resocalc.get_next_item_coord(self)
        #y2 += self._resocalc.get_next_item_coord(self)
        #y1 += self._resocalc.get_next_item_coord(self)
        #y2 += self._resocalc.get_next_item_coord(self)
        h = x1-x2
        w = y1-y2
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = gray[int(y2):(int(y2)+int(w)),int(x2):(int(x2)+int(h))]
        cv2.imshow("output", gray)
        cv2.waitKey(0)
        filename = "{}.png".format(os.getpid())
        cv2.imwrite(filename, gray)
        text = pytesseract.image_to_string(Image.open(filename))
        os.remove(filename)
        print(text)
        return cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)

    def check_mainscreen(self, image):
        print('Check Mainscreen')
        mainscreen = 0

        height, width, _ = image.shape
        gray = image[int(height) - int(round(height / 6)):int(height),
               0: int(int(width) / 4)]
        original = gray
        height_, width_, _ = gray.shape
        radMin = int((width / float(6.8) - 3) / 2)
        radMax = int((width / float(6) + 3) / 2)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.Canny(gray, 100, 50, apertureSize=3)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, width / 8, param1=100, param2=15, minRadius=radMin,
                                   maxRadius=radMax)
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                if x < width_ - width_ / 3:
                    cv2.circle(original, (x, y), r, (0, 255, 0), 4)
                    mainscreen += 1
                    raidhash = original[y - r - 1:y + r + 1, x - r - 1:x + r + 1]
                    cv2.imshow("output", np.hstack([raidhash]))
                    cv2.waitKey(0)

        if mainscreen > 0:
            print("Found Avatar.")
            return True
        return False
        

ap = argparse.ArgumentParser()
ap.add_argument("-i", "--image", required = True, help = "Path to the image")
ap.add_argument("-m", "--mode", required = True, help = "Type of Image")
args = vars(ap.parse_args())

test = testimage(args["image"], args["mode"])


