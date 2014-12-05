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
import unittest
import time
import logging
import pytz


# starts on a monday
_dates = [datetime.date(2014, 11, 24 + _x) for _x in xrange(7)]
_weekdays = {d.strftime('%a'): d.weekday() for d in _dates}
_days = {d.strftime('%a'): d for d in _dates}

# this is useful instead of using datetime.datetime.min because it allows us to
# add and subtract timezone offsets without throwing RangeError.
_DT_MIN = datetime.datetime.min + datetime.timedelta(days=3)


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

    def __init__(self):
        self.server_dt_utc = _DT_MIN
        self.set_utc("Mon 00:00")

    def set_utc(self, s):
        self.server_dt_utc = dt_from_str(s)

    @abc.abstractmethod
    def record_activity(self, untrusted_client_dt):
        pass

    @abc.abstractmethod
    def streak_length(self, tzoffset=None):
        pass


class StreakTestMixin(object):

    @abc.abstractproperty
    def user(self):
        raise Exception()

    def record_activity_at_utc(self, utc_dt_or_str):
        utc_dt = dt_from_str(utc_dt_or_str)
        self.user.server_dt_utc = utc_dt
        self.record_activity(utc_dt)

    def record_activity(self, client_dt_or_str):
        self.user.record_activity(dt_from_str(client_dt_or_str))

    def assert_streak(self, x, inconclusive=False):
        if inconclusive:
            if self.user.streak_length() != x:
                raise InconclusiveTestError()
        else:
            self.assertEqual(self.user.streak_length(), x)

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
        self.assert_streak(0)

    def test_leading_edge(self):
        self.record_activity_at_utc("Mon 07:00")
        self.assert_streak(1)

    def test_leading_edge_tz(self):
        self.user.set_utc("Mon 12:00")
        self.record_activity("Mon 02:00")
        self.assert_streak(1)

    def test_streak_is_hot_next_day_after(self):
        self.record_activity_at_utc("Mon 07:00")
        self.user.set_utc("Tue 12:00")
        self.assert_streak(1)

    def test_missed_day_then_expired(self):
        self.record_activity_at_utc("Mon 19:00")
        self.user.set_utc("Wed 18:00")
        self.assert_streak(0)

    def test_missed_day_then_resume(self):
        self.record_activity_at_utc("Mon 19:00")
        self.record_activity_at_utc("Wed 18:00")
        self.assert_streak(1)

    def test_two_sessions_one_day(self):
        self.record_activity_at_utc("Mon 06:00")
        self.record_activity_at_utc("Mon 23:00")
        self.assert_streak(1)

    def test_increment_next_day_early(self):
        self.record_activity_at_utc("Mon 11:00")
        self.record_activity_at_utc("Tue 10:00")
        self.assert_streak(2)

    def test_increment_next_day_later(self):
        self.record_activity_at_utc("Mon 11:00")
        self.record_activity_at_utc("Tue 12:00")
        self.assert_streak(2)

    def test_increment_maximum_interval(self):
        self.record_activity_at_utc("Mon 00:01")
        self.record_activity_at_utc("Tue 23:59")
        self.assert_streak(2)

    def test_quickest_broken_streak(self):
        self.record_activity_at_utc("Mon 23:59")
        self.user.set_utc("Wed 00:01")
        self.assert_streak(0)

    def test_tz_at_utc(self):
        # for someone at UTC, this is a one day streak
        self.record_activity_at_utc("Mon 01:00")
        self.record_activity_at_utc("Mon 23:00")
        self.assert_streak(1)

    def test_tz_at_plus_8(self):
        # for someone at UTC+8, this is actually a two-day streak!
        tzoffset = datetime.timedelta(hours=8)

        self.user.set_utc("Mon 01:00")
        self.record_activity(_dt("Mon 01:00") + tzoffset)
        # (...still monday)

        self.user.set_utc("Mon 23:00")
        self.record_activity(_dt("Mon 23:00") + tzoffset)
        # (...actually Tue 07:00!)

        self.assert_streak(2)

    def test_reject_futuristic_tz(self):
        self.user.set_utc("Mon 23:00")
        self.record_activity(_dt("Mon 23:00") + datetime.timedelta(hours=15))
        self.assert_streak(0)

    def test_reject_past_tz(self):
        self.user.set_utc("Mon 23:00")
        self.record_activity(_dt("Mon 23:00") + datetime.timedelta(hours=-13))
        self.assert_streak(0)

    def test_out_of_order_activity(self):
        # What happens if the user manipulates their clock such that events
        # arrive out of order? TODO(dmnd): it is to be done
        pass

    def test_nz_to_hawaii(self):
        # user does work in New Zealand
        self.user.set_utc("Mon 12:00")
        self.record_activity("Tue 01:00")  # NZ is UTC+13
        self.assert_streak(1)

        # user gets on plane, flies to Hawaii
        # be conservative and pretend he gets there in only 1 hour
        self.user.set_utc("Mon 13:00")
        self.assert_streak(1)

        # now do some work
        self.record_activity("Mon 03:00")  # Hawaii is UTC-10
        self.assert_streak(1)

    def test_nz_to_hawaii_slow(self):
        # TODO(dmnd): convert this to a class?
        # User does some work in New Zealand.
        nztime = _dt("Mon 23:59")
        nzoffset = datetime.timedelta(hours=+13)
        utc_dt = nztime - nzoffset
        self.assert_time_equals(utc_dt, "Mon 10:59", inconclusive=True)
        self.user.set_utc(utc_dt)
        self.record_activity(nztime)
        self.assert_streak(1, inconclusive=True)

        # User gets on plane, flies to Hawaii.
        # It takes a while to get through security.
        utc_dt += datetime.timedelta(hours=25, minutes=2)
        self.user.set_utc(utc_dt)

        # Little does the user know, his clock hasn't updated.
        nztime = utc_dt + nzoffset
        # It's now Wed in NZ:
        self.assert_weekday(nztime, "Wed", inconclusive=True)
        # So when he does some more work, his streak will break :(
        self.record_activity(nztime)
        self.assert_streak(1, inconclusive=True)

        # Now the user's clock updates to Hawaii timezone, where it's actually
        # only Tuesday:
        hioffset = datetime.timedelta(hours=-12)
        hitime = utc_dt + hioffset
        self.assert_weekday(hitime, "Tue", inconclusive=True)
        # When he does more work, the streak should be continued, even though
        # it was broken earlier.
        self.record_activity(hitime)
        self.assert_streak(2)

    def test_hawaii_to_nz(self):
        # user does work in Hawaii
        self.user.set_utc("Mon 12:00")
        self.record_activity("Mon 02:00")
        self.assert_streak(1, inconclusive=True)

        # user gets on plane, flies to New Zealand
        # be conservative and pretend he gets there in only 1 hour
        # self.user.set_utc("Mon 13:00")
        # self.assert_streak(1, inconclusive=True)
        #
        # # now do some work
        # self.record_activity("Tue 02:00")
        # self.assert_streak(2)

    def test_something_else(self):
        # user does work
        # user sets clock way forward
        # user does more work, streak is extended I guess
        # user sets clock back again
        pass


class Cooldown(StreakAlgo):

    def __init__(self, hours, limit):
        super(Cooldown, self).__init__()
        self.cooldown = datetime.timedelta(hours=hours)
        self.expiry = datetime.timedelta(hours=limit)

        self.last_activity = _DT_MIN
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


class Cooldown1648Test(unittest.TestCase, StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        self._user = Cooldown(hours=16, limit=48)


class Cooldown1624Test(unittest.TestCase, StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        self._user = Cooldown(hours=16, limit=24)


class IntervalExtension(StreakAlgo):

    def __init__(self, hours=48):
        super(IntervalExtension, self).__init__()
        self.extension_limit = datetime.timedelta(hours=hours)
        self.last_activity = _DT_MIN
        self.interval_start = _DT_MIN

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


class IntervalExtensionTest(unittest.TestCase, StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        self._user = IntervalExtension()


_ZERO = datetime.timedelta(0)


class LocalTimezone(datetime.tzinfo):
    """A wrapper for a datetime.timedelta"""

    def __init__(self, offset):  # pylint: disable-msg=W0231
        if not isinstance(offset, datetime.timedelta):
            raise ValueError()
        self.offset = offset

    def __repr__(self):
        return easyrepr(self, ["offset"])

    def utcoffset(self, dt):  # pylint: disable-msg=W0613
        return self.offset

    def tzname(self, dt):  # pylint: disable-msg=W0613
        return self.__class__

    def dst(self, dt):  # pylint: disable-msg=W0613
        return _ZERO


def as_local(utc, tzoffset):
    return utc.replace(tzinfo=pytz.utc).astimezone(tz=LocalTimezone(tzoffset))


def easyrepr(obj, attrs=[], sep=', '):  # pylint: disable-msg=W0102
    """A helper function for quickly creating repr strings.
    """
    attrs = sep.join(["%s=%r" % (a, getattr(obj, a)) for a in attrs])
    return "%s(%s)" % (obj.__class__.__name__, attrs)


class Checkoff(StreakAlgo):
    """Similar to interval extension, but pays attention to days.

    This means it's sensitive to timezones, but in return for that extra
    complexity we get a better user experience. Specifically it becomes easy to
    understand the precise time at which the user is eligible to extend their
    streak, and also the precise time at which the streak will reset.

    These times are aligned to the user's local calendar instead of relative to
    the time of their previous activity.
    """

    def __init__(self):
        super(Checkoff, self).__init__()
        self.interval_end_utc = _DT_MIN
        self.interval_end_tz = datetime.timedelta(0)

        self.interval_start_utc = _DT_MIN
        self.interval_start_tz = datetime.timedelta(0)

        self.previous_interval = None

    def __repr__(self):
        return easyrepr(self, [
            "interval_start_utc",
            "interval_start_tz",
            "interval_start_local",
            "interval_end_utc",
            "interval_end_tz",
            "interval_end_local",
            "previous_interval"], sep=',\n')

    @property
    def interval_start_local(self):
        return as_local(self.interval_start_utc, self.interval_start_tz)

    @interval_start_local.setter
    def interval_start_local_setter(self, x):
        self.interval_end_utc = x.astimezone(pytz.utc).replace(tzinfo=None)
        self.interval_end_tz = x.tzinfo.utcoffset(x)

    @property
    def interval_end_local(self):
        return as_local(self.interval_end_utc, self.interval_end_tz)

    @interval_end_local.setter
    def interval_end_local_setter(self, x):
        self.interval_end_utc = x.astimezone(pytz.utc).replace(tzinfo=None)
        self.interval_end_tz = x.tzinfo.utcoffset(x)

    @property
    def previous_interval_local(self):
        return tuple(as_local(t, tz) for t, tz in self.previous_interval)

    def validate_client_dt(self, untrusted_tzoffset):
        """Clamp the client's reported timezone offset to something sane.

        We trust whatever timezone the client claims within a limit.
        If the user is claiming an offset that's too big, we ignore the request
        for the purposes of streaks.
        """

        # Baker Island and Howland Island use this. Both are uninhabited, but
        # we'll charitably assume the user is on a boat. In theory a user can
        # set their clock to the past to extend a streak that would have
        # expired in their local timezone. Examples:
        #
        #  * A user on the the US East coast move their clock 7 hours into the
        #    past. So someone can stay up past midnight but still get credit
        #    for the previous day.
        #  * A user in New Zealand can move their clock back 24 hours into the
        #    past. So they can miss an entire day and still recover.
        tz_offset_min = datetime.timedelta(hours=-12)

        # Line Islands (part of Kiribati) uses this. Lucky for us they don't
        # have DST. (Chatham Islands uses UTC+13:45 in DST, though.) In theory
        # a UTC user can set their clock 14 hours into the future to extend a
        # streak before their local timezone gets there. Examples:
        #
        #  * A user from Hawaii can set their clock forward by 24 hours. So
        #    they can "pre-fill" their streak a day in advance.
        #  * A user on the east coast of the US can move their clock forward
        #    by 19 hours. So once they wake up, they can pre-fill a whole day
        #    in advance too.
        #  * A user from New Zealand can set their clock forward by only a
        #    couple of hours.
        tz_offset_max = datetime.timedelta(hours=+14)

        return tz_offset_min <= untrusted_tzoffset <= tz_offset_max

    def record_activity(self, untrusted_client_dt):
        untrusted_tzoffset = untrusted_client_dt - self.server_dt_utc
        if self.validate_client_dt(untrusted_tzoffset):
            tzoffset = untrusted_tzoffset
        else:
            logging.warning(
                "Ignoring activity because we don't trust the timezone offset")
            return

        # Events should always arrive in order from the perspective of UTC.
        # TODO(dmnd): Once the server time is passed in, log warnings and throw
        # out stale events

        # But it is possible for the local time to "go backwards". The most
        # frequent example is daylight savings. A more extreme example is
        # travelling across the international dateline. Streaks are based on
        # local time, not UTC, so it's possible we need to adjust the start
        # date of an existing streak interval.

        new_local = as_local(self.server_dt_utc, tzoffset)
        print "ordering"
        print "old: {!r}".format(self.interval_start_local)
        print "new: {!r}".format(new_local)
        print "test: {!r}".format(new_local < self.interval_start_local)
        print
        if (self.interval_start_utc is not _DT_MIN and  # cant call _local
                new_local < self.interval_start_local):
            print "out of order event!"
            # Now we have 2 options, because it's possible the new local time
            # is far enough back in time that a previous ended streak will now
            # that ended will now be coniguous. E.g:
            #
            # (a) Grow the current interval backward in time:
            #
            #     A new event comes in on Wed, which is before the current
            #     interval beginning on Thu.
            #
            #     Mon Tue Wed Thu
            #     --|      x  |--
            #
            #     The interval beginning on Thu should now instead on Thu:
            #
            #     Mon Tue Wed Thu
            #     --|     |------
            #
            # (b) Merge the current interval with the previous one:
            #
            #     A new event comes in on Wed, which is before the current
            #     interval beginning on Thu.
            #
            #     Mon Tue Wed Thu
            #     ------|  x  |--
            #
            #     This merges the two previously separate intervals.
            #
            #     Mon Tue Wed Thu
            #     ---------------
            #
            # This next bit of code decides between (a) and (b).
            l = interval_length(self.previous_interval_local[1], new_local)
            if l <= 2:  # case (a) above; merge
                # overwrite the start of the interval to the previous one
                # self.interval_start_local = self.previous_interval[0]
                self.interval_start_utc = self.previous_interval[0][0]
                self.interval_start_tz = self.previous_interval[0][1]

                # now set the end of the interval to whichever is later of:
                #   1. the current event
                #   2. the end of the previous interval
                # self.interval_end_local = max(
                #   new_local, self.previous_interval_local)

                if new_local > self.previous_interval_local[1]:
                    self.interval_end_utc = new_local - tzoffset
                    self.interval_end_tz = tzoffset
                else:
                    self.interval_end_utc = self.previous_interval[1][0]
                    self.interval_end_tz = self.previous_interval[1][1]

                self.previous_interval = None

            else:  # case (b) above; extend
                # self.interval_start_local = new_local
                self.interval_start_utc = self.server_dt_utc
                self.interval_start_tz = tzoffset

        # TODO: it's likely impossible to need to reset after an out of
        # order event, so change this to elif
        if self.has_reset(tzoffset):
            # save the last streak interval (TODO: get this from the calendar)
            self.previous_interval = (
                (self.interval_start_utc, self.interval_start_tz),
                (self.interval_end_utc, self.interval_end_tz))
            self.interval_start_utc = self.server_dt_utc
            self.interval_start_tz = tzoffset

        self.interval_end_utc = self.server_dt_utc
        self.interval_end_tz = tzoffset

    def streak_length(self, tzoffset=None):
        if tzoffset is None:
            # This happens when someone other than the user is looking at the
            # streak. Use whatever the user last reported.
            tzoffset = self.interval_end_tz

        if self.has_reset(tzoffset):
            return 0

        l = interval_length(self.interval_start_local, self.interval_end_local)
        if l < 0:
            print self
        return l

    def has_reset(self, tzoffset):
        interval = interval_length(self.interval_end_local,
                                   as_local(self.server_dt_utc, tzoffset))
        return interval > 2


def interval_length(t1, t2):
    t1d = t1.date()
    t2d = t2.date()
    days = (t2d - t1d).days
    if days >= 0:
        return days + 1
    else:
        return days - 1


class CheckoffTest(unittest.TestCase, StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        self._user = Checkoff()
