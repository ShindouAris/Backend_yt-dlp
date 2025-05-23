import re


YOUTUBE_REGEX = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.(?:com|nl)\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})")
TIKTOK_DEFAULT_REGEX = re.compile(r"https?://(www\.)?tiktok\.com/(?:embed|@([\w\.-]+)/video|t)/(\d+|\w+)")
TIKTOK_VMVT_REGEX = re.compile(r"https?://(?:vm|vt)\.tiktok\.com/(\w+)")
INSTAGRAM_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com(?:/[^/]+)?/(?:tv|reel|share)/([^/?#& ]+)")
FACEBOOK_REGEX = re.compile(r"https?:\/\/(?:www\.)?facebook\.com\/(?:watch\/?\?v=\d+|[A-Za-z0-9\.]+\/videos\/\d+|share\/v\/[A-Za-z0-9_-]+)\/?|https?:\/\/fb\.watch\/[A-Za-z0-9_-]+\/?")

PROVIDERS = {
    "youtube": YOUTUBE_REGEX,
    "tiktok": [TIKTOK_DEFAULT_REGEX, TIKTOK_VMVT_REGEX],
    "instagram": INSTAGRAM_REGEX,
    "facebook": FACEBOOK_REGEX,
}

def get_provider_from_url(url: str) -> str | None:
    for provider, patterns in PROVIDERS.items():
        if isinstance(patterns, list):
            if any(re.search(p, url) for p in patterns):
                return provider
        else:
            if re.search(patterns, url):
                return provider
    return None