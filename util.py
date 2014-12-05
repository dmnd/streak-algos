def easyrepr(obj, attrs=[], sep=', '):  # pylint: disable-msg=W0102
    """A helper function for quickly creating repr strings."""
    attrs = sep.join(["%s=%r" % (a, getattr(obj, a)) for a in attrs])
    return "%s(%s)" % (obj.__class__.__name__, attrs)
