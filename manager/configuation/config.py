from dotenv import load_dotenv
import os
import pathlib

load_dotenv()



PROJECT_ROOT = pathlib.Path(__file__).parent
DOWNLOAD_FOLDER = pathlib.Path('downloads')
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split("||")
UVICORN_FORWARDED_ORIGINS = os.environ.get("FORWARDED_ORIGINS", "*").split("||")
ENABLE_TROLLING_ROUTE = os.environ.get("ENABLE_TROLLING_ROUTE", "False").lower() == "true"
DISABLE_AUTO_CLEANUP = os.environ.get("KEEP_LOCAL_FILES", "False").lower() == "true"
TURNSITE_VERIFICATION = os.environ.get("TURNSITE_VERIFICATION", "False").lower() == "true"
TURNSITE_SECRET_KEY = os.environ.get("TURNSITE_API_SECRECT_KEY", "youshallnotpassanysecretkey")


if os.environ.get("FILE_EXPIRE_TIME") is not None and os.environ.get("FILE_EXPIRE_TIME").isdigit():
    FILE_EXPIRE_TIME: int = int(os.environ.get("FILE_EXPIRE_TIME"))
else:
    FILE_EXPIRE_TIME: int = 300

IS_DEVELOPMENT = os.environ.get("DEVELOPMENT", "False").lower() == "true"
if not IS_DEVELOPMENT:
    SECRET_PRODUCTION_KEY = os.environ.get("SECRET_PRODUCTION_KEY", "youshallnotpassanysecretkey")
    RATE_LIMIT = int(os.environ.get("RATE_LIMIT", 150))
    RATE_WINDOW = int(os.environ.get("RATE_WINDOW", 60))
else:
    SECRET_PRODUCTION_KEY = "when_the_pig_fly"
    RATE_LIMIT = 1000
    RATE_WINDOW = 0