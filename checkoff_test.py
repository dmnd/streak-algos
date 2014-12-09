import collections
import datetime
import logging
import unittest

import util
import streaks


LocalTime = collections.namedtuple("LocalTime", "dt tz")
_ZERO = datetime.timedelta(0)


class Checkoff(streaks.StreakAlgo):
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
        self.interval_start = LocalTime(dt=streaks.DT_MIN, tz=_ZERO)
        self.interval_end = LocalTime(dt=streaks.DT_MIN, tz=_ZERO)
        self.previous_interval = None

    def __repr__(self):
        return util.easyrepr(self, [
            "interval_start",
            "interval_end",
            "previous_interval"], sep=',\n')

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

    def record_activity(self, untrusted_client_dt, utc_dt):
        # Events should always arrive in order from the perspective of UTC.
        if utc_dt < self.interval_end.dt - self.interval_end.tz:
            logging.warning(
                "Ignoring stale event. "
                "updated_utc: %s, utc_dt: %s", self.updated_utc, utc_dt)
            return

        untrusted_tzoffset = untrusted_client_dt - utc_dt
        if self.validate_client_dt(untrusted_tzoffset):
            current = LocalTime(dt=untrusted_client_dt, tz=untrusted_tzoffset)
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

        if current.dt < self.interval_start.dt:
            logging.info("Out of order event")
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
            merged = None
            if self.previous_interval is not None:
                l = interval_length(self.previous_interval[1].dt, current.dt)
                if l < 0:
                    # the new event is arriving before the close of the
                    # previous event! There's no good way to handle this, but
                    # it should be impossible anyway, so raise an exception.
                    raise ValueError("time travel")
                elif l <= 2:
                    # Case (a) above: merge with previous interval.
                    self.interval_start = self.previous_interval[0]
                    if self.interval_end.dt < self.previous_interval[1].dt:
                        self.interval_end = self.previous_interval
                    self.previous_interval = None
                    merged = True
                else:
                    # The new event isn't close enough to the previous one to
                    # matter. Just grow the current interval backward.
                    merged = False
            else:
                merged = False

            if not merged:
                # Case (b) above: grow interval backward.
                self.interval_start = current

        elif self.has_reset(current.dt):
            # Save the last streak interval (TODO: get this from the calendar)
            if self.interval_start.dt is not streaks.DT_MIN:
                self.previous_interval = (self.interval_start,
                                          self.interval_end)
            self.interval_start = current

        # Extend the current interval if needed
        if current.dt > self.interval_end.dt:
            self.interval_end = current
        else:
            logging.info("Ignoring {} as it's before {}".format(
                current, self.interval_end))

    def streak_length(self, basis_dt):
        if self.has_reset(basis_dt):
            return 0

        return interval_length(self.interval_start.dt, self.interval_end.dt)

    def has_reset(self, basis_dt):
        print 'has_reset'
        print self.interval_end.dt
        print basis_dt
        return interval_length(self.interval_end.dt, basis_dt) > 2


def interval_length(t1, t2):
    t1d = t1.date()
    t2d = t2.date()
    days = (t2d - t1d).days
    if days >= 0:
        return days + 1
    else:
        return days - 1


class CheckoffTest(unittest.TestCase, streaks.StreakTestMixin):
    @property
    def user(self):
        return self._user

    def setUp(self):
        streaks.StreakTestMixin.setUp(self)
        self._user = Checkoff()
