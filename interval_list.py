import datetime
import logging

import util

# this is useful instead of using datetime.datetime.min because it allows us to
# add and subtract timezone offsets without throwing RangeError.
_DT_MIN = datetime.datetime.min + datetime.timedelta(days=3)
_ZERO = datetime.timedelta(0)


def interval_length(a_dt, b_dt):
    days = (b_dt.date() - a_dt.date()).days
    if days >= 0:
        return days + 1
    else:
        return days - 1


def are_contiguous_dt(a_dt, b_dt):
    # if the interval spans 3 days, it's too big
    return interval_length(a_dt, b_dt) < 3


def are_contiguous(a_i, b_i):
    return are_contiguous_dt(a_i.end, b_i.begin)


def insert(event_dt, ilist):
    """Insert a new event into the interval list."""

    # This could be an interval tree, but since we only need to append to
    # the (approximate) end, a plain list is efficient enough. Intervals
    # arrive mostly in order with the exception of stuff like daylight
    # savings or travel across time zones.

    x = StreakInterval(event_dt, event_dt)

    # Find an index at which to insert. Start at the end and move backwards
    i = len(ilist)
    while i > 0 and x.begin < ilist[i - 1].begin:
        i -= 1

    ilist.insert(i, x)
    # Now all the interval are sorted by their begin values.

    # Next, check if we need to merge with the previous or next interval.
    def maybe_merge_with_previous(i):
        if i <= 0:
            return i

        print i
        if are_contiguous(ilist[i - 1], ilist[i]):
            ilist[i - 1].end = ilist[i].end
            del ilist[i]
            return i - 1

        return i

    # try to merge with the previous interval
    i = maybe_merge_with_previous(i)

    # now try to merge with the next
    if i + 1 < len(ilist):
        maybe_merge_with_previous(i + 1)


class StreakInterval(object):
    def __init__(self, begin, end):
        self.begin = begin
        self.end = end

    @property
    def length(self):
        return interval_length(self.begin, self.end)

    def __repr__(self):
        return util.easyrepr(self, ['begin', 'end'])


class IntervalList(object):
    """A cleaner implementation of Checkoff."""

    def __init__(self):
        super(IntervalList, self).__init__()
        self.history = []
        self.updated_utc = _DT_MIN
        self.recent_tz = _ZERO

    def __repr__(self):
        return util.easyrepr(self, ["history"])

    def record_activity(self, untrusted_client_dt, utc_dt):
        # Events should always arrive in order from the perspective of UTC.
        if utc_dt < self.updated_utc:
            logging.warning(
                "Ignoring stale event. "
                "updated_utc: %s, utc_dt: %s", self.updated_utc, utc_dt)
            return

        # We trust the client's reported time, to a degree. If it's too crazy,
        # ignore it
        untrusted_tzoffset = untrusted_client_dt - utc_dt
        if not self.validate_client_dt(untrusted_tzoffset):
            logging.warning(
                "Ignoring event due to extreme timezone offset. "
                "untrusted_client_dt: %s, utc_dt: %s",
                untrusted_client_dt, utc_dt)
            # TODO(dmnd): Instead of ignoring, maybe use client's old timezone?
            return

        self.updated_utc = utc_dt
        self.recent_tz = untrusted_tzoffset

        # now insert a new interval to the interval list
        insert(untrusted_client_dt, self.history)

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

    def streak_length(self, basis_dt):
        if not self.history or self.has_reset(basis_dt):
            return 0
        else:
            return self.history[-1].length

    def has_reset(self, basis_dt):
        assert self.history
        return not are_contiguous_dt(self.history[-1].end, basis_dt)
