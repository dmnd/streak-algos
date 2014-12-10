"""Interface for testing different streak algorithms"""

import abc


class StreakInterface(object):
    @abc.abstractmethod
    def record_activity(self, untrusted_client_dt):
        pass

    @abc.abstractmethod
    def streak_length(self, basis_dt):
        pass
