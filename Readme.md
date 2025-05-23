# Video Downloader API

This project provides a FastAPI-based API for downloading videos using `yt-dlp`. It supports fetching available formats, session management for downloads, automatic file cleanup, and can utilize cookies for downloading videos from platforms requiring login (e.g., YouTube).

---

## Features

- **Fetch Video Formats**: Get a list of available video and audio formats for a given URL.
- **Download Videos**: Download videos using `yt-dlp` with user-selected formats.
- **Session Management**: Each download is associated with a unique session ID.
- **Automatic File Cleanup**: Downloaded files are automatically deleted after a configurable timeout (default: 5 minutes) to save storage.
- **Cookie Support**: Uses `cookies.txt` for authenticated downloads (e.g., private videos, member-only content on YouTube).
- **Geo-restriction Check**: Check if a YouTube video is geo-restricted (requires Google API Key).
- **CORS Enabled**: Allows requests from specified origins.

---

## Prerequisites

1.  **Python**: Python 3.8+ installed.
2.  **pip**: Python package manager (usually comes with Python).
3.  **yt-dlp**: While the project uses `yt-dlp` as a library, you don't need to install it separately via command line if you install project dependencies from `requirements.txt`.
4.  **(Optional) Google API Key**: For using the `/geo_check` endpoint. Must be set as `YOUTUBE_V3_APIKEY` environment variable.
5.  **(Optional) Render Account**: If you plan to host the application on Render.

---

## Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ShindouAris/Backend_yt-dlp.git
cd Backend_yt-dlp
```

### 2. Install Dependencies

It's recommended to use a virtual environment:

```bash
python -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

### 3. (Optional) Create `.env` file for API Keys

If you plan to use the geo-restriction check feature, create a `.env` file in the project root with your Google API Key:

```env
YOUTUBE_V3_APIKEY=your_google_api_v3_key_here
```
The application will load this using `python-dotenv`.

### 4. (Optional) Get `cookies.txt` for `Authenticated / pass robot check` Youtube Downloads

To download videos from websites requiring authentication (e.g., YouTube private videos, age-restricted content that needs login, or member-only content), you'll need a `cookies.txt` file.

#### Steps to get `cookies.txt` from YouTube:

1.  Install the **Cookie-Editor** browser extension:
    *   [Chrome Web Store](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
    *   [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)
2. Open a new private browsing/incognito window and log into YouTube.
3. In the same window and same tab from step 1, navigate to:  
   `https://www.youtube.com/robots.txt`  
   (this should be the only private/incognito browsing tab open)
4. Export `youtube.com` cookies from the browser.
5. Close the private browsing/incognito window so that the session is never opened in the browser again.

> **Important**:
> *   The `cookies.txt` file **must** be in the Netscape HTTP Cookie File format.
> *   The very first line of the file **must** be either `# HTTP Cookie File` or `# Netscape HTTP Cookie File`. If it's not, `yt-dlp` may fail to parse it.
> *   This file will be used by `yt-dlp` (via the API) to make authenticated requests. The API itself does not directly handle your login credentials.
> *   The path to this cookie file is specified in `backendv2.py` for the `fetch_format_data` function as `cookiefile="./cookie.txt"`.

### 5. Run the Application Locally

```bash
python backendv2.py
```

The API will be available at `http://127.0.0.1:8000`. You should see log output indicating the server has started, including the `yt-dlp` version being used.

---

## API Endpoints

The base URL for local development is `http://127.0.0.1:8000`.

### 1. **GET / HEAD** `/`

Provides a welcome message, lists available routes, and shows server uptime.

- **Response** (JSON):
  ```json
  {
    "message": "Server is running - [ [root] - ['GET', 'HEAD'] - [/] ][ [get_all_formats] - ['POST'] - [/get_all_format] ][ [download_video] - ['POST'] - [/download] ][ [get_downloaded_file] - ['GET'] - [/files/{session_id}] ][ [check_geo_block] - ['POST'] - [/geo_check] ] - Last restart: <Day Mon DD HH:MM:SS YYYY>"
  }
  ```

### 2. **POST** `/get_all_format`

Fetches available download formats for a given video URL.

- **Request Body** (JSON, `FormatRequest`):
  ```json
  {
    "url": "https://www.youtube.com/watch?v=example"
  }
  ```
  *(The `url` can be for YouTube, Facebook, Instagram, or any other site supported by `yt-dlp`)*

- **Response** (JSON, `FormatResponse`):
  ```json
  {
    "name": "Video Title [video_id].ext", // Example: "ばかみたい [EamxSv3xhoE].webm"
    "formats": [
      {
        "type": "video+audio", // e.g., "video+audio", "audio-only", "video-only"
        "format": "313+251",    // yt-dlp format_id string, used for download
        "label": "2160p (webm) [Audio: 134.2Kbps]", // Human-readable description
        "video_format": "313", // Video part format_id (if applicable)
        "audio_format": "251", // Audio part format_id (if applicable)
        "note": "2160p"        // Additional note from yt-dlp (e.g., resolution, "medium", "low")
      },
      // ... more FormatInfo objects
      {
        "type": "audio-only",
        "format": "251",
        "label": "Audio only: 134.2kbps (webm)",
        "video_format": null,
        "audio_format": "251",
        "note": "medium"
      }
    ]
  }
  ```
  *(The structure of the `formats` array items is based on the `FormatInfo` Pydantic model. See the example JSON files like `youtube_get_format_payload.json` for more examples of `yt-dlp` output which this API processes.)*

### 3. **POST** `/download`

Initiates a video download for the specified URL and format.

- **Request Body** (JSON, `DownloadRequest`):
  ```json
  {
    "url": "https://www.youtube.com/watch?v=example",
    "format": "313+251" // format_id string obtained from /get_all_format.
                       // Defaults to "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" if not provided.
  }
  ```
  *(The `format` string should be one of the `format` values (e.g., `137+140`, `251`) returned by the `/get_all_format` endpoint, or a generic `yt-dlp` format selector.)*

- **Successful Response** (JSON, `DownloadResponse`):
  ```json
  {
    "message": "Download completed",
    "filename": "Video Title.ext",       // Proposed filename for the download
    "download_link": "/files/<session_id>", // Relative link to retrieve the file
    "details": "File has been downloaded successfully", // Optional additional details
    "yt_dlp_output": null                 // Optional raw output from yt-dlp, if captured
  }
  ```
  *(`<session_id>` will be a UUID4 string, e.g., `550e8400-e29b-41d4-a716-446655440000`. The `details` and `yt_dlp_output` fields may be `null` or absent if not applicable.)*

- **Error Response** (HTTP 500, text/plain or JSON with detail):
  ```
  Download failed
  ```
  *(Or a JSON response if a specific HTTPException is raised by the server.)*

### 4. **GET** `/files/<session_id>`

Retrieve the downloaded file associated with a `session_id`. The file is served as an `application/octet-stream`.

- **Path Parameter**:
    - `session_id` (string, UUID4 format): The session ID generated during the `/download` request.

- **Example URL**:
  ```
  http://127.0.0.1:8000/files/550e8400-e29b-41d4-a716-446655440000
  ```
  *(Replace `550e8400-e29b-41d4-a716-446655440000` with the actual `session_id` from the `/download` response.)*

- **Response**:
    - **Success (HTTP 200)**: The file data. The `Content-Disposition` header will suggest the filename.
    - **Error (HTTP 404)**: If the session ID is invalid, the file does not exist (e.g., expired and cleaned up), or no matching file extension is found within the session's download folder.
      ```json
      {
        "detail": "File not found: downloads/<session_id>"
      }
      ```

#### Python Script Example to Download the File:

This script demonstrates how to call the `/download` endpoint and then use its response to download the file from `/files/<session_id>`.

```python
import requests
import os
import json # For parsing JSON response

# Replace with your actual API base URL if not running locally
api_base_url = "http://127.0.0.1:8000"

# --- Step 1: Call /download endpoint (Example) ---
video_url_to_download = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Example video
# You should first call /get_all_format to choose a specific format_id
# For simplicity, we'll use a common format or let the server default.
# Example: chosen_format_id = "18" (a common mp4 format for YouTube (360p))
# Or provide a more specific one: chosen_format_id = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"

download_payload = {
    "url": video_url_to_download,
    # "format": chosen_format_id # Optional: API uses a default if not specified
}

print(f"Requesting download for URL: {video_url_to_download}")
session_id = None
suggested_filename = "downloaded_video.mp4" # Default filename

try:
    download_response_req = requests.post(f"{api_base_url}/download", json=download_payload)
    download_response_req.raise_for_status() # Raise an exception for HTTP errors

    if download_response_req.status_code == 200:
        response_data = download_response_req.json() # Parse the DownloadResponse
        print(f"/download response: {json.dumps(response_data, indent=2)}")

        session_id = response_data.get("download_link", "").split('/')[-1]
        if response_data.get("filename"):
            suggested_filename = response_data.get("filename")

        print(f"Download initiated. Session ID: {session_id}, Filename: {suggested_filename}")
        if response_data.get("details"):
            print(f"Details: {response_data.get('details')}")
    else:
        print(f"Error from /download endpoint: {download_response_req.status_code} - {download_response_req.text}")

except requests.exceptions.RequestException as e:
    print(f"Error calling /download endpoint: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Server response: {e.response.text}")

# --- Step 2: Download the file using session_id from /files endpoint ---
if session_id:
    file_download_url = f"{api_base_url}/files/{session_id}"
    print(f"Attempting to download file from: {file_download_url}")

    try:
        # It might take a moment for the server to finish downloading and preparing the file
        # You might want to add a small delay or retry logic here if needed
        # import time
        # time.sleep(5) # Optional: wait a few seconds

        response = requests.get(file_download_url, stream=True)
        response.raise_for_status() # Raise an exception for HTTP errors

        if response.status_code == 200:
            # Ensure the 'download_output' directory exists
            output_dir = "download_output"
            os.makedirs(output_dir, exist_ok=True)
            local_filepath = os.path.join(output_dir, suggested_filename)

            with open(local_filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192): # 8KB chunks
                    f.write(chunk)
            print(f"File '{suggested_filename}' downloaded successfully to '{local_filepath}'!")
        # No need for specific 404 check here as raise_for_status() would handle it

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Failed to download file. Status code: 404. File not found or session expired.")
            print(f"Server response: {e.response.text}")
        else:
            print(f"Failed to download file. HTTP error: {e}")
            print(f"Server response: {e.response.text}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the file download request: {e}")
else:
    print("Could not proceed to download file as session_id was not obtained.")

```

### 5. **POST** `/geo_check`

Checks if a YouTube video is geo-restricted. This endpoint requires the `YOUTUBE_V3_APIKEY` environment variable to be set on the server.

- **Request Body** (JSON, `FormatRequest`):
  ```json
  {
    "url": "https://www.youtube.com/watch?v=some_video_id"
  }
  ```
- **Response** (JSON, `GeoblockData`):
  ```json
  {
    "url": "https://www.youtube.com/watch?v=some_video_id",
    "allowed_country": ["US", "CA"], // List of allowed country codes (e.g., ISO 3166-1 alpha-2)
    "blocked_country": ["DE", "FR"]   // List of blocked country codes
  }
  ```
  *(The `allowed_country` and `blocked_country` lists will contain strings representing country codes. If the information is not available or the video is not restricted, these lists might be empty. The exact content depends on the output of the underlying `is_geo_restricted` function from `geoblock_checker.py` and its compatibility with this `GeoblockData` model.)*
- **Error Response** (HTTP 401, JSON): If `YOUTUBE_V3_APIKEY` is not configured on the server.
  ```json
  {
    "detail": "This backend is not configured for geochecking"
  }
  ```

---

## Hosting on Render

## 1. Create a Render Account

1. **Do it yourself!**

### 2. Create a New Web Service on Render

1.  Log in to your [Render](https://render.com/) dashboard.
2.  Click **New +** > **Web Service**.
3. Select Public GitHub repository.
4. Paste the repo in (https://github.com/ShindouAris/Backend_yt-dlp.git)

Should look like this:
<img src="assets/render_deploy_clone_repo.png">

### 3. Configure the Service

-   **Name**: Choose a unique name for your service (e.g., `my-video-downloader-api`).
-   **Region**: Select a region geographically close to you or your users.
-   **Branch**: Select the branch to deploy (e.g., `main` or `master`).
-   **Root Directory**: Leave as is if your `backendv2.py` and `requirements.txt` are in the root of the repository. If they are in a subdirectory, specify it here.
-   **Runtime**: Select **Python**. Render will typically pick a recent Python 3 version. You can specify one via `PYTHON_VERSION` environment variable if needed.
-   **Build Command**:
    ```bash
    pip install -r requirements.txt --pre
    ```
-   **Start Command**:
    ```bash
    python backendv2.py
    ```
    *(The application in `backendv2.py` is hardcoded to run on host `0.0.0.0` and port `8000`. Render automatically maps its external port (80/443 for HTTP/HTTPS) to the port your application listens on internally, as long as your app listens on `0.0.0.0`. Port `8000` should work fine.)*

-   **Instance Type**: Choose a plan (e.g., the Free plan for testing/small projects).

Should look like this:
<img src="assets/render_deploy_config.png">
### 4. Add Environment Variables (and Secret Files if needed)

Navigate to the **Environment** tab for your newly created service.

-   **Environment Variables**:
    -   If you plan to use the `/geo_check` endpoint, add an environment variable:
        -   **Key**: `YOUTUBE_V3_APIKEY`
        -   **Value**: Your Google API v3 key.
    -   Optionally, set `PYTHON_VERSION` (e.g., `3.10.12`) if you need a specific Python version.
-   **Secret Files**:
    -   If you need `cookies.txt` for authenticated downloads:
        1.  Click **Add Secret File**.
        2.  **Filename**: `cookies.txt`
        3.  **Contents**: Paste the entire content of your local `cookies.txt` file.
            This file will be created in your project's root directory at build/runtime on Render, making it available to `backendv2.py`.
        4. Click **Save**.<br/>

Should look like this:
<img src="assets/render_deploy_env_sec_config.png">
### 5. Deploy

Click **Create Web Service**. Render will start the build and deployment process. You can monitor the logs under the **Events** or **Logs** tab. Once deployed, your API will be accessible via the URL provided by Render (e.g., `https://your-service-name.onrender.com`).

---

## Notes

-   **`cookies.txt`**: This file is crucial for accessing content that requires login (e.g., private YouTube videos, member-only content). Ensure it's correctly formatted and placed in the project root (or configured as a secret file on Render). Cookies can expire, so you might need to update this file periodically.
-   **`downloads` Folder**: This folder is created automatically in the project's working directory (e.g., `/opt/render/project/src/downloads` on Render, or `./downloads` locally) to store downloaded files temporarily. On platforms like Render, this storage is ephemeral and will be lost if the instance restarts or redeploys.
-   **File Auto-Deletion**: Files in the `downloads/<session_id>/` folder are automatically deleted 5 minutes after their corresponding session is created (i.e., after the download completes). This is managed by the `FileSession.auto_delete_file_task` in `backendv2.py`. The `timeout` is currently set to 300 seconds.
-   **CORS Origins**: The API is configured in `backendv2.py` to allow requests from `https://youtube-downloader-nine-drab.vercel.app` and `http://localhost:5173`. If your frontend is hosted on a different domain, you'll need to add it to the `allow_origins` list in the `CORSMiddleware` setup.

---

## Troubleshooting

1.  **Cookies Not Working / Authentication Fails**:
    *   Ensure `cookies.txt` is present in the project's root directory (or correctly configured as a secret file on Render).
    *   Verify the `cookies.txt` file is in the correct Netscape format and the first line is exactly `# HTTP Cookie File` or `# Netscape HTTP Cookie File`. Any deviation can cause parsing errors.
    *   Cookies expire. If downloads that previously worked start failing, try re-exporting your cookies and updating the `cookies.txt` file.
2.  **`File not found` (404 for `/files/<session_id>`)**:
    *   Double-check that the `session_id` in the URL is correct and matches the one received from a successful `/download` response.
    *   The file might have been deleted by the auto-cleanup process (default is 5 minutes after download completion). You may need to initiate the download again.
    *   Check server logs for any errors during the download or file storage process. On Render, ensure the `downloads` directory is writable by the application.
3.  **Deployment Issues on Render**:
    *   Carefully review the Render deployment logs (under **Events**) for any build errors (e.g., missing packages, Python version issues) or runtime errors (e.g., application failing to start).
    *   Ensure all dependencies listed in `requirements.txt` are compatible with the Render environment (Linux).
    *   Verify your Start Command (`python backendv2.py`) is correct and `backendv2.py` is in the expected location.
4.  **Geo-check Fails (401 Unauthorized or Pydantic Validation Error)**:
    *   For 401: Confirm the `YOUTUBE_V3_APIKEY` environment variable is correctly set in your Render service's environment settings. Verify that the API key is valid, active, and has the "YouTube Data API v3" enabled in your Google Cloud Console project.
    *   For Pydantic Validation Error (if `/geo_check` returns an unexpected structure): The `is_geo_restricted` function (in `geoblock_checker.py`) might be returning data that doesn't match the `GeoblockData` model (which expects `url`, `allowed_country`, `blocked_country`). You may need to adjust the `GeoblockData` model in `backendv2.py` or modify `is_geo_restricted` to return data in the expected format.
5.  **Error Fetching Formats (HTTP 500 from `/get_all_format`)**:
    *   The provided video URL might be invalid, or the video could be private, deleted, or heavily restricted.
    *   `yt-dlp` might be encountering issues with that specific website or URL structure. You can check the `yt-dlp` GitHub issues page for similar problems.
    *   If the content is from a site requiring login and you haven't provided a valid `cookies.txt`, this could be the cause. Check server logs for more detailed error messages from `yt-dlp`.

---

## FAQ

1.  **How do I change the download format?**
    -   First, call the `/get_all_format` endpoint with the video URL. This will return a list of available formats, each with a `format` string (e.g., `"137+140"`, `"251"`) and a human-readable `label`.
    -   In the request body of the `/download` endpoint, set the `format` field to the desired `format` string from the `/get_all_format` response. For example: `{"url": "...", "format": "137+140"}`. If the `format` field is omitted, the API will use the default: `"bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"`.

2.  **Can I download playlists?**
    -   No, this specific API is designed for downloading single videos at a time. While `yt-dlp` itself supports playlist downloads, the API endpoints (`/get_all_format`, `/download`) expect a URL pointing to a single video.

3.  **How are large files handled? Are there size limits?**
    -   The API downloads the video to the server's temporary storage (`downloads` folder) before you can retrieve it via `/files/<session_id>`.
    -   The primary limitation will be the disk space available on the server where the API is hosted. Free tiers of platforms like Render usually have limited (and ephemeral) disk space.
    -   Downloaded files are automatically deleted 5 minutes after the download completes to conserve space. If you need to store files longer or handle very large files consistently, you might need to:
        *   Modify the `timeout` in the `auto_delete_file_task` method within the `FileSession` class in `backendv2.py`.
        *   Consider a hosting plan with more disk space or integrate external storage (like S3).

4.  **How do I get the `cookies.txt` file?**
    -   Please refer to the detailed instructions in the "Local Setup" section under "4. (Optional) Get `cookies.txt` for Authenticated Downloads". This involves:
        1.  Installing a browser extension like Cookie-Editor.
        2.  Logging into the website (e.g., YouTube) in your browser.
        3.  Using the extension to export cookies in **Netscape** format.
        4.  Saving this data into a file named `cookies.txt` in the project's root directory.
    -   **Crucially**, ensure the first line of `cookies.txt` is either `# HTTP Cookie File` or `# Netscape HTTP Cookie File`.

---
## License

This project is licensed under the MIT License. (Assuming MIT License as is common for such open-source projects. If a specific `LICENSE` file exists in the repository, it takes precedence.)

<img src="https://i.pinimg.com/736x/9c/d9/2f/9cd92f33e4c3e47b30697e3e587fcc99.jpg" alt="gomen"/>
