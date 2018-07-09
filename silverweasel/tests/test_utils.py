import unittest
import arrow

from silverweasel.utils import parse_datetime


class DateParseTest(unittest.TestCase):
    def test_parse_past(self):
        timezone = 'America/New_York'
        shouldbe = arrow.get('01/15/2018 07:00 PM', 'MM/DD/YYYY HH:mm A',
                             tzinfo=timezone)
        parsed = parse_datetime('01/15/0018 07:00 PM', timezone)
        self.assertEqual(parsed, shouldbe)
