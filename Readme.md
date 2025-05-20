# Video Downloader API

This project is a Flask-based API for downloading videos using `yt-dlp`. It supports session management, automatic file cleanup, and cookie-based authentication for downloading videos from platforms requiring login.

---

## Features

- Download videos using `yt-dlp` with custom formats.
- Manage download sessions with automatic cleanup after a timeout.
- Serve downloaded files via API endpoints.
- Support for cookies to handle authenticated downloads.

---

## Prerequisites

1. **Python**: Ensure Python 3.8+ is installed.
2. **pip**: Python package manager for installing dependencies.
3. **yt-dlp**: A powerful video downloader.
4. **Render Account**: For hosting the application.

---

## Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ShindouAris/Backend_yt-dlp.git
cd Backend_yt-dlp
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```
### 3. Get `cookies.txt`

Google it bro, i will fix this later<br/>
<img src="https://i.ibb.co/VYc8pVDN/stamp0238.png">

### 4. Run the Application Locally

```bash
python main.py
```

The API will be available at `http://127.0.0.1:8080`.

---

## API Endpoints

### 1. **POST** `/download`

Download a video.

- **Request Body** (JSON):
  ```json
  {
    "url": "https://www.youtube.com/watch?v=example",
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
  }
  ```
- **Response** (JSON):
  ```json
  {
    "message": "Download completed",
    "filename": "example.mp4",
    "download_link": "/files/<session_id>",
    "details": "File has been downloaded successfully"
  }
  ```

### 2. **GET** `/files/<session_id>`

Retrieve the downloaded file.

---

## Hosting on Render

### 1. Create a New Web Service

1. Log in to [Render](https://render.com/).
2. Click **New** > **Web Service**.
3. Connect your GitHub repository.

### 2. Configure the Service

- **Environment**: Python 3.8+
- **Build Command**:
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command**:
  ```bash
  python backendv2.py
  ```
- **Port**: 8080

### 3. Deploy

Click **Deploy** to start the deployment process. Once deployed, the API will be accessible via the Render-provided URL.

---

## Notes

- Ensure `cookies.txt` is included in the project directory for authenticated downloads.
- The `downloads` folder is automatically created for storing downloaded files.
- Files are automatically deleted after 5 minutes to save storage.

---

## Troubleshooting

1. **Cookies Not Working**: Ensure `cookies.txt` is valid and placed in the root directory.
2. **File Not Found**: Check if the session ID is valid and the file exists in the `downloads` folder.
3. **Deployment Issues**: Verify the Render logs for errors and ensure all dependencies are installed.

---

## FAQ
1. **How do I change the download format?**
   - Modify the `format` field in the request body of the `/download` endpoint.
2. **Can I download playlists?**
    - No, `yt-dlp` supports playlist downloads, but this API is designed for single video downloads only.
3. **How do I handle large files?**
    - The API automatically deletes files after 5 minutes. If you need to keep them longer, consider modifying the `cleanup` function in `backendv2.py`.
4. **How do I get the ``cookie.txt`` file ?**
    - Google it dude, there are many tutorials on how to get it.
    - The cookie file should be in the NetScape format, which is the default for the extension.
    - Note that the cookies file must be in Mozilla/Netscape format and the first line of the cookies file must be either `# HTTP Cookie File` or `# Netscape HTTP Cookie File`


---
## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
