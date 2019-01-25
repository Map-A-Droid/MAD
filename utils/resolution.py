import logging

log = logging.getLogger(__name__)


class Resocalculator(object):
    def __init__(self):
        self._screen_x = 0
        self._screen_y = 0
        self._xyratio = 0

    def get_x_y_ratio(self, x, y):
        self._xyratio = float(y) / float(x)
        return True

    def get_coords_quest_menu(self):
        click_x = (int(self._screen_x) / 1.07)
        click_y = int(self._screen_y) - (int(self._screen_x) / 3.86)
        return click_x, click_y

    def get_gym_click_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 1.5)
        return click_x, click_y

    def get_gym_spin_coords(self):
        click_y = int(self._screen_y) / 2
        click_x1 = int(self._screen_x) / 3
        click_x2 = int(self._screen_x) - int(click_x1)
        return click_x1, click_x2, click_y

    def get_close_main_button_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 7.57)
        return click_x, click_y

    def get_delete_quest_coords(self):
        click_y = int(self._screen_x) / 1.2
        click_x = int(self._screen_x) / 1.07
        return click_x, click_y

    def get_swipe_item_amount(self):
        if int(self._xyratio) > 2:
            click_x1 = int(self._screen_x) / 1.46
            click_x2 = int(self._screen_x) / 1.26
            click_y = int(self._screen_y) - (int(self._screen_x) / 0.87)
        else:
            click_x1 = int(self._screen_x) / 1.46
            click_x2 = int(self._screen_x) / 1.26
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.02)
        return click_x1, click_x2, click_y

    def get_confirm_delete_quest_coords(self):
        click_x = int(self._screen_x) / 2
        if int(self._xyratio) > 2:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.02)
        else:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.22)
        return click_x, click_y

    def get_item_menu_coords(self):
        click_x = int(self._screen_x) / 1.28
        click_y = int(self._screen_y) - (int(self._screen_x) / 3.27)
        return click_x, click_y

    def get_delete_item_coords(self):
        click_x = int(self._screen_x) / 1.09
        click_y = int(self._screen_y) - (int(self._screen_x) / 0.68)
        return click_x, click_y

    def get_next_item_coord(self):
        y = int(self._screen_x) / 2.84
        return y

    def get_confirm_delete_item_coords(self):
        click_x = int(self._screen_x) / 2
        if int(self._xyratio) > 2:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.2)
        else:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.5)
        return click_x, click_y

        return click_x, click_y

    def get_leave_mon_coords(self):
        click_x = int(self._screen_x) / 11.25
        click_y = int(self._screen_x) / 6.82
        return click_x, click_y

    def get_weather_popup_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 12)
        return click_x, click_y

    def get_weather_warn_popup_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 4)
        return click_x, click_y
