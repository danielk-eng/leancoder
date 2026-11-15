"""Dotted-path access into nested config dictionaries."""


def get_nested(cfg, path, default=None):
    """Return cfg['a']['b']['c'] for path 'a.b.c', or `default` if missing."""
    cur = cfg
    for part in path.split("."):
        cur = cur[part]
    return cur


def require(cfg, path):
    sentinel = object()
    value = get_nested(cfg, path, sentinel)
    if value is sentinel:
        raise KeyError(path)
    return value
