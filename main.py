from flask import Flask, request, jsonify, send_from_directory
import os
import uuid
import pathlib
import datetime
import threading
import time
from shutil import rmtree
import yt_dlp

# --- Configuration ---
app = Flask(__name__)
PROJECT_ROOT = pathlib.Path(__file__).parent
DOWNLOAD_FOLDER = pathlib.Path('downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

class DownloadResponse:
    def __init__(self, message, filename=None, download_link=None, details=None, yt_dlp_output=None):
        self.message = message
        self.filename = filename
        self.download_link = download_link
        self.details = details
        self.yt_dlp_output = yt_dlp_output

    def to_dict(self):
        return {
            "message": self.message,
            "filename": self.filename,
            "download_link": self.download_link,
            "details": self.details,
            "yt_dlp_output": self.yt_dlp_output,
        }

class FileSession:
    def __init__(self):
        self.sessions = []
        self.storage = {}
        self.lock = threading.Lock()
        self.cleanup_thread = threading.Thread(target=self.auto_delete_file_task, daemon=True)
        self.cleanup_thread.start()

    def add_session(self, session_id, file_path=None):
        with self.lock:
            self.sessions.append(session_id)
            if file_path:
                self.storage[session_id] = (file_path, datetime.datetime.utcnow().timestamp())

    def auto_delete_file_task(self):
        while True:
            time.sleep(60)
            timeout = 300
            expired_sessions = []
            now = datetime.datetime.utcnow().timestamp()

            with self.lock:
                for session_id, (file_path, created_time) in list(self.storage.items()):
                    if now - created_time >= timeout:
                        if file_path.exists():
                            rmtree(file_path)
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    self.sessions.remove(session_id)
                    del self.storage[session_id]

    def clear_sessions(self):
        with self.lock:
            for session_id in self.sessions:
                file_path = self.storage.get(session_id)
                if file_path and file_path[0].exists():
                    rmtree(file_path[0])
                    del self.storage[session_id]
            self.sessions.clear()

file_session = FileSession()

def generate_uuid():
    return str(uuid.uuid4())

def run_yt_dlp_download(url, format_option, output):
    ydl_opts = {
        'format': format_option,
        'outtmpl': str(output) + '/%(title)s.%(ext)s',
        'keepvideo': False,
        'noplaylist': False,
        'noprogress': True,
        'ignoreerrors': True,
        'quiet': False,
        'verbose': False,
        'no_warnings': True,
        'simulate': False,
        'extract_flat': False
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([yt_dlp.utils.sanitize_url(url)])
            return {"success": True, "file_location": output}
        except yt_dlp.utils.DownloadError:
            return {"success": False}

def get_file_name(url, format_option, output_template):
    ydl_opts = {
        "format": format_option,
        "outtmpl": output_template,
        "quiet": True,
        "simulate": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info_dict)
            return filename
        except yt_dlp.utils.DownloadError as e:
            raise Exception(f"Error extracting file name: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url')
    format_option = data.get('format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    session_id = generate_uuid()
    output = DOWNLOAD_FOLDER / session_id
    output.mkdir(parents=True, exist_ok=True)

    try:
        result = run_yt_dlp_download(url, format_option, output)
        if result["success"]:
            filename = get_file_name(url, format_option, str(output) + '/%(title)s.%(ext)s')
            file_session.add_session(session_id, output)
            response = DownloadResponse(
                message="Download completed",
                filename=filename,
                download_link=f"/files/{session_id}",
                details="File has been downloaded successfully"
            )
            return jsonify(response.to_dict())
        else:
            return jsonify({'error': 'Download failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/files/<session_id>', methods=['GET'])
def get_downloaded_file(session_id):
    file_path = DOWNLOAD_FOLDER / session_id
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404

    for file in file_path.glob("*.mp4"):
        if file.is_file():
            return send_from_directory(file_path, file.name, as_attachment=True)

    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)