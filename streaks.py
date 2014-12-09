#!/usr/bin/env python

# This file is a bit strange, a lot of tests are "expected" to fail because the
# algorithm they use is too simple. But this is confusing because nothing
# records which tests are supposed to fail. So, for now, know that 19 tests
# should fail.
#
# All CheckoffTest tests should pass though, because it's an algorithm that
# works in all circumstances (but has the drawback that it needs to deal with
# user timezones).
#
# TODO: warning! we need to record both last_activity for historical reasons
# but also (interval_end, tz), because they are different things!!


"""Testing out different streak algorithms"""

import abc
import datetime
import time


# starts on a monday
_dates = [datetime.date(2014, 11, 24 + _x) for _x in xrange(7)]
_weekdays = {d.strftime('%a'): d.weekday() for d in _dates}
_days = {d.strftime('%a'): d for d in _dates}


# this is useful instead of using datetime.datetime.min because it allows us to
# add and subtract timezone offsets without throwing RangeError.
DT_MIN = datetime.datetime.min + datetime.timedelta(days=3)


def dt_from_str(s):
    """Python's time libs are fun."""
    if isinstance(s, basestring):
        dow, time_s = s.split()
        date = _days[dow]
        time_ts = time.strptime(time_s, '%H:%M')
        time_t = datetime.time(hour=time_ts.tm_hour, minute=time_ts.tm_min)
        return datetime.datetime.combine(date, time_t)
    else:
        # assume it's a datetime already and return it
        return s


# for convenience
_dt = dt_from_str


class InconclusiveTestError(Exception):
    """Mocking, test environment or other testing preconditions failed.

    Because of setup failuers, the test cannot pass or fail: the result is
    undefined.
    """
    def __init__(self, message=("Test inconclusive due to "
                                "error in preconditions or setup")):
        super(InconclusiveTestError, self).__init__(message)


class StreakAlgo(object):
    @abc.abstractmethod
    def record_activity(self, untrusted_client_dt):
        pass

    @abc.abstractmethod
    def streak_length(self, basis_dt):
        pass


class StreakTestMixin(object):

    def setUp(self):
        self.advance_utc_time("Mon 00:00")

    @abc.abstractproperty
    def user(self):
        raise Exception()

    def advance_utc_time(self, utc_dt_or_str):
        """Also sets local_dt.

        Used for advancing time without recording activity.
        """
        dt = _dt(utc_dt_or_str)
        self.local_dt = dt
        self.utc_dt = dt

    def record_activity(self, client_dt_or_str):
        self.local_dt = dt_from_str(client_dt_or_str)
        self.user.record_activity(self.local_dt, self.utc_dt)

    def set_utc_then_record_activity(self, utc_dt_or_str):
        self.advance_utc_time(utc_dt_or_str)
        self.record_activity(utc_dt_or_str)

    def assert_streak(self, x, inconclusive=False):
        if inconclusive:
            if self.user.streak_length(self.local_dt) != x:
                raise InconclusiveTestError()
        else:
            self.assertEqual(self.user.streak_length(self.local_dt), x)

    def assert_weekday(self, dt, weekday, inconclusive=False):
        if not inconclusive:
            raise NotImplementedError()  # TODO(dmnd)

        if dt.weekday() != _weekdays[weekday]:
            raise InconclusiveTestError()

    def assert_time_equals(self, dt, s, inconclusive=False):
        if not inconclusive:
            raise NotImplementedError()  # TODO(dmnd)

        if dt != _dt(s):
            raise InconclusiveTestError()

    def test_initial(self):
        print self.user
        self.assert_streak(0)

    def test_leading_edge(self):
        self.set_utc_then_record_activity("Mon 07:00")
        self.assert_streak(1)

    def test_leading_edge_tz(self):
        self.advance_utc_time("Mon 12:00")
        self.record_activity("Mon 02:00")
        self.assert_streak(1)

    def test_streak_is_hot_next_day_after(self):
        self.set_utc_then_record_activity("Mon 07:00")
        self.advance_utc_time("Tue 12:00")
        self.assert_streak(1)

    def test_missed_day_then_expired(self):
        self.set_utc_then_record_activity("Mon 19:00")
        self.advance_utc_time("Wed 18:00")
        self.assert_streak(0)

    def test_missed_day_then_resume(self):
        self.set_utc_then_record_activity("Mon 19:00")
        self.set_utc_then_record_activity("Wed 18:00")
        self.assert_streak(1)

    def test_two_sessions_one_day(self):
        self.set_utc_then_record_activity("Mon 06:00")
        self.set_utc_then_record_activity("Mon 23:00")
        self.assert_streak(1)

    def test_increment_next_day_early(self):
        self.set_utc_then_record_activity("Mon 11:00")
        self.set_utc_then_record_activity("Tue 10:00")
        self.assert_streak(2)

    def test_increment_next_day_later(self):
        self.set_utc_then_record_activity("Mon 11:00")
        self.set_utc_then_record_activity("Tue 12:00")
        self.assert_streak(2)

    def test_increment_maximum_interval(self):
        self.set_utc_then_record_activity("Mon 00:01")
        self.set_utc_then_record_activity("Tue 23:59")
        self.assert_streak(2)

    def test_quickest_broken_streak(self):
        self.set_utc_then_record_activity("Mon 23:59")
        self.advance_utc_time("Wed 00:01")
        self.assert_streak(0)

    def test_tz_at_utc(self):
        # for someone at UTC, this is a one day streak
        self.set_utc_then_record_activity("Mon 01:00")
        self.set_utc_then_record_activity("Mon 23:00")
        self.assert_streak(1)

    def test_tz_at_plus_8(self):
        # for someone at UTC+8, this is actually a two-day streak!
        tzoffset = datetime.timedelta(hours=8)

        self.advance_utc_time("Mon 01:00")
        self.record_activity(_dt("Mon 01:00") + tzoffset)
        # (...still monday)

        self.advance_utc_time("Mon 23:00")
        self.record_activity(_dt("Mon 23:00") + tzoffset)
        # (...actually Tue 07:00!)

        self.assert_streak(2)

    def test_reject_futuristic_tz(self):
        self.advance_utc_time("Mon 23:00")
        self.record_activity(_dt("Mon 23:00") + datetime.timedelta(hours=15))
        self.assert_streak(0)

    def test_reject_past_tz(self):
        self.advance_utc_time("Mon 23:00")
        self.record_activity(_dt("Mon 23:00") + datetime.timedelta(hours=-13))
        self.assert_streak(0)

    def test_nz_to_hawaii(self):
        # user does work in New Zealand
        self.advance_utc_time("Mon 12:00")
        self.record_activity("Tue 01:00")  # NZ is UTC+13
        self.assert_streak(1)

        # user gets on plane, flies to Hawaii
        # be conservative and pretend he gets there in only 1 hour
        self.advance_utc_time("Mon 13:00")
        self.assert_streak(1)

        # Now do some work.
        self.record_activity("Mon 03:00")  # Hawaii is UTC-10
        # Even though it's Monday here, Tuesday has already been marked off, so
        # the streak length is 2.
        self.assert_streak(2)

    def test_nz_to_hawaii_slow(self):
        # TODO(dmnd): convert this to a class?
        # User does some work in New Zealand.
        nztime = _dt("Mon 23:59")
        nzoffset = datetime.timedelta(hours=+13)
        utc_dt = nztime - nzoffset
        self.assert_time_equals(utc_dt, "Mon 10:59", inconclusive=True)
        self.advance_utc_time(utc_dt)
        self.record_activity(nztime)
        self.assert_streak(1, inconclusive=True)

        # User gets on plane, flies to Hawaii.
        # It takes a while to get through security.
        utc_dt += datetime.timedelta(hours=25, minutes=2)
        self.advance_utc_time(utc_dt)

        # Little does the user know, his clock hasn't updated.
        nztime = utc_dt + nzoffset
        # It's now Wed in NZ:
        self.assert_weekday(nztime, "Wed", inconclusive=True)
        # So when he does some more work, his streak will break :(
        self.record_activity(nztime)
        self.assert_streak(1, inconclusive=True)

        # Now the user's clock updates to the Hawaii timezone, where it's
        # actually only Tuesday:
        hioffset = datetime.timedelta(hours=-12)
        hitime = utc_dt + hioffset
        self.assert_weekday(hitime, "Tue", inconclusive=True)
        # When he does more work, the streak should be continued, even though
        # it was broken earlier.
        self.record_activity(hitime)
        self.assert_streak(3)

    def test_hawaii_to_nz(self):
        # user does work in Hawaii
        hitime = _dt("Mon 23:59")
        hioffset = datetime.timedelta(hours=-12)
        utc_dt = hitime - hioffset
        self.assert_weekday(utc_dt, "Tue", inconclusive=True)
        self.advance_utc_time(utc_dt)
        self.record_activity(hitime)
        self.assert_streak(1, inconclusive=True)

        # user gets on plane, flies to New Zealand
        # be conservative and pretend he gets there in only 1 hour
        utc_dt += datetime.timedelta(hours=1)
        self.advance_utc_time(utc_dt)

        # now do some work
        nzoffset = datetime.timedelta(hours=+13)
        nztime = utc_dt + nzoffset
        self.assert_weekday(nztime, "Wed", inconclusive=True)

        # The streak is only one day long, because the user missed out on Tue!
        self.record_activity(nztime)
        self.assert_streak(1)
