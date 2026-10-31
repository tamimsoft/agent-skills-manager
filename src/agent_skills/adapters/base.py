"""Base adapter interface (Phase 1 placeholder)."""


class BaseAdapter(object):
    name = None

    def __init__(self, config=None):
        self.config = config or {}