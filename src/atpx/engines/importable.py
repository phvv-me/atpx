from importlib.util import find_spec


def is_importable(module: str) -> bool:
    """Whether `module` can be imported here, without importing it.

    module: the import name to probe.
    """
    try:
        return find_spec(module) is not None
    except ModuleNotFoundError:
        return False
