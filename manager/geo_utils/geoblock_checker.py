import aiohttp
import pycountry
from pydantic import BaseModel
from urllib.parse import urlparse, parse_qs

class GeoblockData(BaseModel):
    url: str
    allowed_country: list
    blocked_country: list

def get_video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path.startswith("/clip"):
        raise NotImplementedError("Clip video ID extraction not supported in this script.")
    elif parsed.path.startswith("/shorts/"):
        return parsed.path.split("/shorts/")[1]
    else:
        query = parse_qs(parsed.query)
        return query.get("v", [""])[0]

async def is_geo_restricted(video_id: str, youtube_api_key: str) -> GeoblockData:
    api_url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=contentDetails&id={video_id}&key={youtube_api_key}"
    )
    async with aiohttp.ClientSession() as session:

        response = await session.get(api_url)
        if not response.ok:
            raise Exception(f"API request failed with status code {response.status}: {response.text}")

        data = await response.json()
        print(data)
        items = data.get("items", [])
        if not items:
            raise ValueError("No video data returned.")
        all_countries = {country.alpha_2 for country in pycountry.countries}
        content_details = items[0].get("contentDetails", {})
        region_restriction = content_details.get("regionRestriction", {})
        allowed: list = region_restriction.get("allowed", [])
        blocked = sorted(all_countries - set(allowed))

        return GeoblockData(
            url = video_url,
            allowed_country = allowed_country,
            blocked_country = blocked
        )

# Example usage
if __name__ == "__main__":
    # https://console.cloud.google.com/marketplace/product/google/youtube.googleapis.com?q=search&referrer=search&inv=1&invt=AbyIBQ&project=regal-net-453801-u0
    YOUTUBE_API_KEY = "YOUR_API_KEY" # Replace with your api key

    # ショートムービー「リコリス・リコイル Friends are thieves of time.」｜第６話「Brief respite」, Blocked in every country except japan
    video_url = "https://www.youtube.com/watch?v=DmCuZPrKpOQ"

    import asyncio
    loop = asyncio.get_event_loop()
    all_countries = {country.alpha_2 for country in pycountry.countries}
    try:
        video_id = get_video_id(video_url)
        allowed = loop.run_until_complete(is_geo_restricted(video_id, YOUTUBE_API_KEY))
        if allowed:
            allowed_country = sorted(all_countries - set(allowed))
            print("This video is blocked in the following countries:")
            print(", ".join(all_countries))
            print("Allowed in the following countries:")
            print(", ".join(allowed)) # Should return JP
    except Exception as e:
        print("Error:", e)
