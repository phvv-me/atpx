import fire

from . import NAME
from .workspace import workspace


def main() -> None:
    """Expose the workspace verbs as the tool's command, named after the package."""
    fire.Fire(workspace(), name=NAME)


if __name__ == "__main__":
    main()
