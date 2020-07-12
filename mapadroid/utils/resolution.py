class Resocalculator(object):
    def __init__(self):
        self._screen_x = 0
        self._screen_y = 0
        self._xyratio = 0
        self._y_offset = 0
        self._x_offset = 0

    def get_x_y_ratio(self, x, y, x_offset=0, y_offset=0):
        self._xyratio = float(y) / float(x)
        self._x_offset = x_offset
        self._y_offset = y_offset
        return True

    def get_coords_quest_menu(self):
        click_x = (int(self._screen_x) / 1.07)
        click_y = int(self._screen_y) - (int(self._screen_x) / 3.86)
        if self._y_offset > 0:
            return click_x + self._x_offset, click_y - self._y_offset - 55
        else:
            return click_x, click_y

    def get_quest_listview(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) / 5.82
        return click_x + self._x_offset, click_y + self._y_offset

    def get_gym_click_coords(self):
        click_x = int(self._screen_x) / 2
        if float(self._xyratio) >= 2:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.30)
        elif float(self._xyratio) >= 1.9:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.35)
        elif float(self._xyratio) >= 1.7:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.40)
        elif float(self._xyratio) < 1.7:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.45)
        return click_x + self._x_offset, click_y - self._y_offset

    def get_gym_spin_coords(self):
        click_y = int(self._screen_y) / 2
        click_x1 = int(self._screen_x) / 3
        click_x2 = int(self._screen_x) - int(click_x1)
        return click_x1 + self._x_offset, click_x2 + self._x_offset, click_y + self._y_offset

    def get_ggl_account_coords(self):
        temp_offset = int(self._screen_y) / 24.61
        click_x = int(self._screen_x) / 2
        click_y = (int(self._screen_y) / 2) + int(temp_offset)
        return click_x, click_y

    def get_close_main_button_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 7.57)
        if self._y_offset > 0:
            return click_x + self._x_offset, click_y - self._y_offset - 55
        else:
            return click_x, click_y

    def get_delete_quest_coords(self):
        if float(self._xyratio) > 2.1:
            click_y = int(self._screen_x) / 1.1
            click_x = int(self._screen_x) / 1.07
        elif float(self._xyratio) >= 2:
            click_y = int(self._screen_x) / 1.195
            click_x = int(self._screen_x) / 1.07
        elif float(self._xyratio) >= 1.7:
            click_y = int(self._screen_x) / 1.2
            click_x = int(self._screen_x) / 1.07
        elif float(self._xyratio) < 1.7:
            click_y = int(self._screen_x) / 1.2
            click_x = int(self._screen_x) / 1.07
        return click_x + self._x_offset, click_y + self._y_offset

    def get_swipe_item_amount(self):
        if float(self._xyratio) > 2:
            click_x1 = int(self._screen_x) / 1.46
            click_x2 = int(self._screen_x) / 1.26
            click_y = int(self._screen_y) - (int(self._screen_x) / 0.90)
        elif float(self._xyratio) >= 1.9:
            click_x1 = int(self._screen_x) / 1.46
            click_x2 = int(self._screen_x) / 1.26
            click_y = int(self._screen_y) - (int(self._screen_x) / 0.94)
        elif float(self._xyratio) >= 1.7:
            click_x1 = int(self._screen_x) / 1.46
            click_x2 = int(self._screen_x) / 1.26
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.02)
        elif float(self._xyratio) < 1.7:
            click_x1 = int(self._screen_x) / 1.46
            click_x2 = int(self._screen_x) / 1.26
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.12)
        return click_x1, click_x2, click_y

    def get_confirm_delete_quest_coords(self):
        click_x = int(self._screen_x) / 2
        if float(self._xyratio) > 2:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.06)
        elif float(self._xyratio) >= 1.9:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.11)
        elif float(self._xyratio) >= 1.7:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.22)
        elif float(self._xyratio) < 1.7:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.37)
        return click_x, click_y

    def get_item_menu_coords(self):
        click_x = int(self._screen_x) / 1.28
        click_y = int(self._screen_y) - (int(self._screen_x) / 3.27)
        return click_x + self._x_offset, click_y - self._y_offset

    def get_delete_item_coords(self):
        if float(self._xyratio) > 2:
            click_x = int(self._screen_x) / 1.09
            click_y = int(self._screen_y) - (int(self._screen_x) / 0.58)
        elif float(self._xyratio) >= 1.9:
            click_x = int(self._screen_x) / 1.09
            click_y = int(self._screen_y) - (int(self._screen_x) / 0.61)
        elif float(self._xyratio) >= 1.7:
            click_x = int(self._screen_x) / 1.09
            click_y = int(self._screen_y) - (int(self._screen_x) / 0.68)
        elif float(self._xyratio) < 1.7:
            click_x = int(self._screen_x) / 1.09
            click_y = int(self._screen_y) - (int(self._screen_x) / 0.77)
        return click_x + self._x_offset, click_y + self._y_offset

    def get_inventory_text_diff(self):
        if float(self._xyratio) > 2.1:
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.61) - \
                    (int(self._screen_y) - (int(self._screen_x) / 0.58))
        elif float(self._xyratio) > 2:
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.60) - \
                    (int(self._screen_y) - (int(self._screen_x) / 0.57))
        elif float(self._xyratio) >= 1.9:
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.62) - \
                    (int(self._screen_y) - (int(self._screen_x) / 0.59))
        elif float(self._xyratio) >= 1.7:
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.715) - \
                    (int(self._screen_y) - (int(self._screen_x) / 0.68))
        elif float(self._xyratio) < 1.7:
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.82) - \
                    (int(self._screen_y) - (int(self._screen_x) / 0.77))
        return y1

    def get_delete_item_text(self):
        if float(self._xyratio) > 2.1:
            x1 = int(self._screen_x) / 1.3
            x2 = int(self._screen_x) / 3.3
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.61)
            y2 = int(self._screen_y) - (int(self._screen_x) / 0.58)
        elif float(self._xyratio) > 2:
            x1 = int(self._screen_x) / 1.3
            x2 = int(self._screen_x) / 3.3
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.60)
            y2 = int(self._screen_y) - (int(self._screen_x) / 0.57)
        elif float(self._xyratio) >= 1.9:
            x1 = int(self._screen_x) / 1.3
            x2 = int(self._screen_x) / 3.3
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.62)
            y2 = int(self._screen_y) - (int(self._screen_x) / 0.59)
        elif float(self._xyratio) >= 1.7:
            x1 = int(self._screen_x) / 1.3
            x2 = int(self._screen_x) / 3.3
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.715)
            y2 = int(self._screen_y) - (int(self._screen_x) / 0.68)
        elif float(self._xyratio) < 1.7:
            x1 = int(self._screen_x) / 1.3
            x2 = int(self._screen_x) / 3.3
            y1 = int(self._screen_y) - (int(self._screen_x) / 0.82)
            y2 = int(self._screen_y) - (int(self._screen_x) / 0.77)
        return x1 + self._x_offset, x2 + self._x_offset, y1 + self._y_offset, y2 + self._y_offset

    def get_next_item_coord(self):
        y = int(self._screen_x) / 2.84
        return y

    def get_confirm_delete_item_coords(self):
        click_x = int(self._screen_x) / 2
        if float(self._xyratio) > 2:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.25)
        elif float(self._xyratio) >= 1.9:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.3)
        elif float(self._xyratio) >= 1.7:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.5)
        elif float(self._xyratio) < 1.7:
            click_y = int(self._screen_y) - (int(self._screen_x) / 1.7)
        return click_x, click_y

    def get_leave_mon_coords(self):
        click_x = int(self._screen_x) / 11.25
        click_y = int(self._screen_x) / 6.82
        return click_x + self._x_offset, click_y + self._y_offset

    def get_weather_popup_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 12)
        return click_x + self._x_offset, click_y + self._y_offset

    def get_weather_warn_popup_coords(self):
        click_x = int(self._screen_x) / 2
        click_y = int(self._screen_y) - (int(self._screen_x) / 4)
        return click_x + self._x_offset, click_y + self._y_offset
