import unittest

import streaks_test
import interval_list


class IntervalListTest(unittest.TestCase, streaks_test.StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        streaks_test.StreakTestMixin.setUp(self)
        self._user = interval_list.IntervalList()
