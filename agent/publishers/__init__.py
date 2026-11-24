from .base import DryRunPublisher, Publisher
from .stubs import PLATFORM_PUBLISHERS


def get_publisher(platform: str, dry_run: bool) -> Publisher:
    if dry_run:
        return DryRunPublisher(platform)
    if platform not in PLATFORM_PUBLISHERS:
        raise ValueError(f"No publisher for platform '{platform}'")
    return PLATFORM_PUBLISHERS[platform]()
