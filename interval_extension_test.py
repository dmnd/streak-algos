import datetime
import unittest

import streaks


class IntervalExtension(streaks.StreakInterface):

    def __init__(self, hours=48):
        super(IntervalExtension, self).__init__()
        self.extension_limit = datetime.timedelta(hours=hours)
        self.last_activity = streaks.DT_MIN
        self.interval_start = streaks.DT_MIN

    def record_activity(self, untrusted_client_dt):
        if self.has_reset():
            self.interval_start = self.server_dt_utc

        self.last_activity = self.server_dt_utc

    def streak_length(self, tzoffset=None):
        if self.has_reset():
            return 0

        return (self.last_activity - self.interval_start).days + 1

    def has_reset(self):
        return self.server_dt_utc - self.last_activity > self.extension_limit


class IntervalExtensionTest(unittest.TestCase, streaks.StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        self._user = IntervalExtension()
