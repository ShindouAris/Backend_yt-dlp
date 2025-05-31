import re

YOUTUBE_REGEX = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.(?:com|nl)\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})")
TIKTOK_DEFAULT_REGEX = re.compile(r"https?://(www\.)?tiktok\.com/(?:embed|@([\w\.-]+)/video|t)/(\d+|\w+)")
TIKTOK_VMVT_REGEX = re.compile(r"https?://(?:vm|vt)\.tiktok\.com/(\w+)")
INSTAGRAM_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com(?:/[^/]+)?/(?:tv|reel|share)/([^/?#& ]+)")
FACEBOOK_REGEX = re.compile(r"https?:\/\/(?:www\.)?facebook\.com\/(?:watch\/?\?v=\d+|[A-Za-z0-9\.]+\/videos\/\d+|share\/v\/[A-Za-z0-9_-]+)\/?|https?:\/\/fb\.watch\/[A-Za-z0-9_-]+\/?")
X_STATUS_REGEX = re.compile(r"^(https?:\/\/)?(www\.)?x\.com\/[a-zA-Z0-9_]{1,15}\/status\/\d+$")
FB_STORY_REGEX = re.compile(r"^https?://(www\.)?(web\.)?facebook\.com/stories/[\w.-]+/[\w=]+")

pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.(?:com|nl)\/watch\?v=|youtu\.be\/)(?P<sub_id>[a-zA-Z0-9_-]{11})"
yt_list_pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.(?:com|nl)\/watch\?v=|youtu\.be\/)(?P<sub_id>[a-zA-Z0-9_-]{11})(?:&(?P<params>.+))?"

PROVIDERS = {
    "youtube": YOUTUBE_REGEX,
    "tiktok": [TIKTOK_DEFAULT_REGEX, TIKTOK_VMVT_REGEX],
    "instagram": INSTAGRAM_REGEX,
    "facebook": FACEBOOK_REGEX,
    "x": X_STATUS_REGEX,
    "facebook_story": FB_STORY_REGEX
}

def get_provider_from_url(url: str) -> str :
    for provider, patterns in PROVIDERS.items():
        if isinstance(patterns, list):
            if any(re.search(p, url) for p in patterns):
                return provider
        else:
            if re.search(patterns, url):
                return provider
    return "yt_dlp_mixed"

def is_youtube_playlist(url: str) -> bool:
    return bool(re.search(yt_list_pattern, url))

def resolve_url(url: str) -> str:
    video_id = re.search(pattern, url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id.group('sub_id')}"

    return url

def normalize_facebook_url(url: str) -> str:
    url = url.replace("web.facebook.com", "facebook.com")
    if not FB_STORY_REGEX.match(url):
        raise ValueError("❌ Invalid Facebook story URL.")
    return url