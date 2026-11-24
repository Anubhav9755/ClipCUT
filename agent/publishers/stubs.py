"""Real platform adapters go here, one per platform.

Each needs API access that has to be requested first (see README -> "Platform access").
Fill these in as each approval comes through; the scheduler already calls them.
"""
from .base import Publisher


class YouTubePublisher(Publisher):
    platform = "youtube"
    # YouTube Data API v3: videos.insert (resumable upload). OAuth consent screen + quota needed.
    # Set madeForKids correctly. Shorts = vertical video under 3 min with #Shorts in title/description.

    def publish(self, variant: dict) -> str:
        raise NotImplementedError("YouTube adapter not connected yet")


class InstagramPublisher(Publisher):
    platform = "instagram"
    # Meta Graph API: create a REELS media container from a PUBLIC video_url, then media_publish.
    # Upload the file to public storage first (e.g. Cloudflare R2) and pass its URL.

    def publish(self, variant: dict) -> str:
        raise NotImplementedError("Instagram adapter not connected yet")


class FacebookPublisher(Publisher):
    platform = "facebook"
    # Meta Graph API: POST /{page-id}/video_reels (same Meta app + review as Instagram).

    def publish(self, variant: dict) -> str:
        raise NotImplementedError("Facebook adapter not connected yet")


class TikTokPublisher(Publisher):
    platform = "tiktok"
    # TikTok Content Posting API. Posts stay private until the app passes TikTok's audit.

    def publish(self, variant: dict) -> str:
        raise NotImplementedError("TikTok adapter not connected yet")


class XPublisher(Publisher):
    platform = "x"
    # X API v2: upload media (chunked), then POST /2/tweets. Pay-per-use billing.

    def publish(self, variant: dict) -> str:
        raise NotImplementedError("X adapter not connected yet")


PLATFORM_PUBLISHERS = {
    "youtube": YouTubePublisher,
    "instagram": InstagramPublisher,
    "facebook": FacebookPublisher,
    "tiktok": TikTokPublisher,
    "x": XPublisher,
}
