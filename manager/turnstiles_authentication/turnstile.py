from aiohttp import ClientSession

class Turnstile:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def verify_token(self, token: str, ip_address: str) -> bool:
        payload = {
            "secret": self.secret_key,
            "response": token,
            "remoteip": ip_address
        }

        async with ClientSession() as session:
            async with session.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=payload) as response:
                data = await response.json()
                return data["success"]

