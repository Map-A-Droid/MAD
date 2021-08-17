class ResolutionCalculator:
    def __init__(self):
        self._screen_size_x: int = 0
        self._screen_size_y: int = 0
        self._x_y_ratio: float = 0.0
        self._y_offset: int = 0
        self._x_offset: int = 0

    @property
    def y_offset(self) -> int:
        return self._y_offset

    @y_offset.setter
    def y_offset(self, new_y_offset: int) -> None:
        if new_y_offset < 0:
            raise ValueError("Unreasonable y-offset: {}", new_y_offset)
        self._y_offset = new_y_offset

    @property
    def x_offset(self) -> int:
        return self._x_offset

    @x_offset.setter
    def x_offset(self, new_x_offset: int) -> None:
        if new_x_offset < 0:
            raise ValueError("Unreasonable x-offset: {}", new_x_offset)
        self._x_offset = new_x_offset

    @property
    def screen_size_x(self) -> int:
        return self._screen_size_x

    @screen_size_x.setter
    def screen_size_x(self, new_size_x: int) -> None:
        if new_size_x < 1:
            raise ValueError("Unreasonable screen dimension: {}", new_size_x)
        self._screen_size_x = new_size_x
        self.__update_ratio()

    @property
    def screen_size_y(self) -> int:
        return self._screen_size_y

    @screen_size_y.setter
    def screen_size_y(self, new_size_y: int) -> None:
        if new_size_y < 1:
            raise ValueError("Unreasonable screen dimension: {}", new_size_y)
        self._screen_size_y = new_size_y
        self.__update_ratio()

    def __update_ratio(self) -> None:
        if self._screen_size_x > 0 and self._screen_size_y > 0:
            self._x_y_ratio: float = float(self._screen_size_y) / float(self._screen_size_x)

    def get_coords_quest_menu(self):
        click_x = self._screen_size_x / 1.07
        click_y = self.screen_size_y - self.screen_size_x / 3.86
        if self._y_offset > 0:
            return click_x + self._x_offset, click_y - self._y_offset - 55
        else:
            return click_x, click_y

    def get_quest_listview(self):
        click_x = self._screen_size_x / 2.0
        click_y = self.screen_size_y / 5.82
        return click_x + self._x_offset, click_y + self._y_offset

    def get_gym_click_coords(self):
        click_x = int(self._screen_size_x) / 2.0
        if self._x_y_ratio >= 2.1:
            click_y = self.screen_size_y - self._screen_size_x / 1.22
        elif self._x_y_ratio >= 2:
            click_y = self.screen_size_y - self._screen_size_x / 1.27
        elif self._x_y_ratio >= 1.9:
            click_y = self.screen_size_y - self._screen_size_x / 1.32
        elif self._x_y_ratio >= 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.37
        elif self._x_y_ratio < 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.42
        return click_x + self._x_offset, click_y - self._y_offset

    def get_gym_spin_coords(self):
        click_y = self.screen_size_y / 2.0
        click_x1 = self._screen_size_x / 3.0
        click_x2 = self._screen_size_x - int(click_x1)
        return click_x1 + self._x_offset, click_x2 + self._x_offset, click_y + self._y_offset

    def get_close_main_button_coords(self):
        click_x = self._screen_size_x / 2.0
        click_y = self.screen_size_y - self._screen_size_x / 7.57
        if self._y_offset > 0:
            return click_x + self._x_offset, click_y - self._y_offset - 55
        else:
            return click_x, click_y

    def get_delete_quest_coords(self):
        if self._x_y_ratio > 2.1:
            click_y = self._screen_size_x / 1.1
            click_x = self._screen_size_x / 1.07
        elif self._x_y_ratio >= 2.0:
            click_y = self._screen_size_x / 1.195
            click_x = self._screen_size_x / 1.07
        elif self._x_y_ratio >= 1.7:
            click_y = self._screen_size_x / 1.2
            click_x = self._screen_size_x / 1.07
        elif self._x_y_ratio < 1.7:
            click_y = self._screen_size_x / 1.2
            click_x = self._screen_size_x / 1.07
        return click_x + self._x_offset, click_y + self._y_offset

    def get_click_item_minus(self):
        click_x = self._screen_size_x / 3.7
        if self._x_y_ratio > 2.0:
            click_y = self.screen_size_y - self._screen_size_x / 0.90
        elif self._x_y_ratio >= 1.9:
            click_y = self.screen_size_y - self._screen_size_x / 0.94
        elif self._x_y_ratio >= 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.02
        elif self._x_y_ratio < 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.12
        return click_x, click_y

    def get_confirm_delete_quest_coords(self):
        click_x = self._screen_size_x / 2.0
        if self._x_y_ratio > 2.0:
            click_y = self.screen_size_y - self._screen_size_x / 1.06
        elif self._x_y_ratio >= 1.9:
            click_y = self.screen_size_y - self._screen_size_x / 1.11
        elif self._x_y_ratio >= 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.22
        elif self._x_y_ratio < 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.37
        return click_x, click_y

    def get_item_menu_coords(self):
        click_x = self._screen_size_x / 1.28
        click_y = self.screen_size_y - self._screen_size_x / 3.27
        return click_x + self._x_offset, click_y - self._y_offset

    def get_delete_item_coords(self):
        if self._x_y_ratio > 2.0:
            click_x = self._screen_size_x / 1.09
            click_y = self.screen_size_y - self._screen_size_x / 0.58
        elif self._x_y_ratio >= 1.9:
            click_x = self._screen_size_x / 1.09
            click_y = self.screen_size_y - self._screen_size_x / 0.61
        elif self._x_y_ratio >= 1.7:
            click_x = self._screen_size_x / 1.09
            click_y = self.screen_size_y - self._screen_size_x / 0.68
        elif self._x_y_ratio < 1.7:
            click_x = self._screen_size_x / 1.09
            click_y = self.screen_size_y - self._screen_size_x / 0.77
        return click_x + self._x_offset, click_y + self._y_offset

    def get_inventory_text_diff(self):
        if self._x_y_ratio > 2.1:
            y1 = self.screen_size_y - self._screen_size_x / 0.61 - (self.screen_size_y - self._screen_size_x / 0.58)
        elif self._x_y_ratio > 2.0:
            y1 = self.screen_size_y - self._screen_size_x / 0.60 - (self.screen_size_y - self._screen_size_x / 0.57)
        elif self._x_y_ratio >= 1.9:
            y1 = self.screen_size_y - self._screen_size_x / 0.62 - (self.screen_size_y - self._screen_size_x / 0.59)
        elif self._x_y_ratio >= 1.7:
            y1 = self.screen_size_y - self._screen_size_x / 0.715 - (self.screen_size_y - self._screen_size_x / 0.68)
        elif self._x_y_ratio < 1.7:
            y1 = self.screen_size_y - self._screen_size_x / 0.82 - (self.screen_size_y - self._screen_size_x / 0.77)
        return y1

    def get_delete_item_text(self):
        if self._x_y_ratio > 2.1:
            x1 = self._screen_size_x / 1.3
            x2 = self._screen_size_x / 3.3
            y1 = self.screen_size_y - self._screen_size_x / 0.61
            y2 = self.screen_size_y - self._screen_size_x / 0.58
        elif self._x_y_ratio > 2.0:
            x1 = self._screen_size_x / 1.3
            x2 = self._screen_size_x / 3.3
            y1 = self.screen_size_y - self._screen_size_x / 0.60
            y2 = self.screen_size_y - self._screen_size_x / 0.57
        elif self._x_y_ratio >= 1.9:
            x1 = self._screen_size_x / 1.3
            x2 = self._screen_size_x / 3.3
            y1 = self.screen_size_y - self._screen_size_x / 0.62
            y2 = self.screen_size_y - self._screen_size_x / 0.59
        elif self._x_y_ratio >= 1.7:
            x1 = self._screen_size_x / 1.3
            x2 = self._screen_size_x / 3.3
            y1 = self.screen_size_y - self._screen_size_x / 0.715
            y2 = self.screen_size_y - self._screen_size_x / 0.68
        elif self._x_y_ratio < 1.7:
            x1 = self._screen_size_x / 1.3
            x2 = self._screen_size_x / 3.3
            y1 = self.screen_size_y - self._screen_size_x / 0.82
            y2 = self.screen_size_y - self._screen_size_x / 0.77
        return x1 + self._x_offset, x2 + self._x_offset, y1 + self._y_offset, y2 + self._y_offset

    def get_next_item_coord(self):
        return self._screen_size_x / 2.84

    def get_confirm_delete_item_coords(self):
        click_x = self._screen_size_x / 2.0
        if self._x_y_ratio > 2.0:
            click_y = self.screen_size_y - self._screen_size_x / 1.25
        elif self._x_y_ratio >= 1.9:
            click_y = self.screen_size_y - self._screen_size_x / 1.3
        elif self._x_y_ratio >= 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.5
        elif self._x_y_ratio < 1.7:
            click_y = self.screen_size_y - self._screen_size_x / 1.7
        return click_x, click_y
