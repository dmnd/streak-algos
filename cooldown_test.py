import unittest
import datetime

import streaks


class Cooldown(streaks.StreakAlgo):

    def __init__(self, hours, limit):
        super(Cooldown, self).__init__()
        self.cooldown = datetime.timedelta(hours=hours)
        self.expiry = datetime.timedelta(hours=limit)

        self.last_activity = streaks.DT_MIN
        self.streak_level = 0

    def has_reset(self):
        return self.server_dt_utc - self.last_activity >= self.expiry

    def record_activity(self, untrusted_client_dt):
        if self.has_reset():
            self.streak_level = 0

        if self.server_dt_utc - self.last_activity >= self.cooldown:
            self.streak_level += 1

        self.last_activity = self.server_dt_utc

    def streak_length(self, tzoffset=None):
        if self.has_reset():
            return 0
        else:
            return self.streak_level


class Cooldown1648Test(unittest.TestCase, streaks.StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        self._user = Cooldown(hours=16, limit=48)


class Cooldown1624Test(unittest.TestCase, streaks.StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        self._user = Cooldown(hours=16, limit=24)
