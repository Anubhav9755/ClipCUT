class Publisher:
    """One class per platform. publish() uploads the video and returns the post URL."""
    platform = "base"

    def publish(self, variant: dict) -> str:
        raise NotImplementedError


class DryRunPublisher(Publisher):
    """Logs what would be posted. Used until real API access is approved."""

    def __init__(self, platform: str):
        self.platform = platform

    def publish(self, variant: dict) -> str:
        tags = " ".join("#" + h for h in variant["hashtags"])
        print(f"  [DRY RUN] {self.platform}/{variant['lang']}: {variant['title']!r}")
        print(f"            {variant['caption']} {tags}")
        print(f"            file: {variant['video_path']}")
        return f"dry-run://{self.platform}/{variant['id']}"
