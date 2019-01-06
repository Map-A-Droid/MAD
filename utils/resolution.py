import logging


log = logging.getLogger(__name__)

class Resocalculator(object):
    def __init__(self):
        self._screen_x = 0
        self._screen_y = 0
        self._xyratio = 0
        
        
    def get_x_y_ratio(self, x, y):
        self._xyratio = float(y) / float(x)
        log.error(self._xyratio)
        return True
        
    def get_coords_quest_menu(self):
        if self._xyratio < 2:
            click_x = int(self._screen_y) - (int(self._screen_x) / 3.8)
            click_y = int(self._screen_y) - (int(self._screen_x) / 12.85)
            return click_x, click_y
            
    def get_gym_click_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 1.5)
        return click_x, click_y