import argparse
import sys
sys.path.append("..")
from utils.resolution import Resocalculator
import cv2

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
            
    

ap = argparse.ArgumentParser()
ap.add_argument("-i", "--image", required = True, help = "Path to the image")
ap.add_argument("-m", "--mode", required = True, help = "Type of Image")
args = vars(ap.parse_args())



tet = testimage(args["image"], args["mode"])


