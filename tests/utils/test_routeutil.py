import datetime
import unittest

from freezegun import freeze_time

from mapadroid.utils.collections import Location
from mapadroid.utils.routeutil import check_walker_value_type


class TestRouteutils(unittest.TestCase):
    @freeze_time(datetime.datetime(2022, 3, 29, 22, 0, 1))
    def test_check_walker_value_type(self):
        period_value: str = "00:00-01:00"
        location_ger: Location = Location(52.516499, 13.380591)
        ger_in_period: bool = check_walker_value_type(period_value, location_ger)
        self.assertEqual(ger_in_period, True)  # add assertion here

        period_value: str = "03:00-05:00"
        location_ger: Location = Location(52.516499, 13.380591)
        ger_in_period: bool = check_walker_value_type(period_value, location_ger)
        self.assertEqual(ger_in_period, False)  # add assertion here

if __name__ == '__main__':
    unittest.main()
