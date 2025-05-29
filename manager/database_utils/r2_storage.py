import boto3
from botocore.client import Config
import os
from typing import Optional, BinaryIO
from datetime import datetime, timedelta
import logging

log = logging.getLogger(__name__)

class R2Storage:
    def __init__(self):
        self.enabled = os.environ.get("USE_R2_STORAGE", "false").lower() == "true"
        if not self.enabled:
            return

        self.account_id = os.environ.get("R2_ACCOUNT_ID")
        self.access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
        self.secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.environ.get("R2_BUCKET_NAME")

        if not all([self.account_id, self.access_key_id, self.secret_access_key, self.bucket_name]):
            raise ValueError("Missing required R2 configuration")

        self.s3 = boto3.client(
            's3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(signature_version='s3v4'),
        )

    def upload_file(self, file_path: str, object_name: Optional[str] = None) -> bool:
        """Upload a file to R2 storage"""
        if not self.enabled:
            return False

        if object_name is None:
            object_name = os.path.basename(file_path)

        try:
            log.info(f"Uploading file to R2: {file_path} -> {object_name}")
            self.s3.upload_file(file_path, self.bucket_name, object_name)
            return True
        except Exception as e:
            log.error(f"Error uploading file to R2: {e}")
            return False

    def upload_fileobj(self, file_obj: BinaryIO, object_name: str) -> bool:
        """Upload a file-like object to R2 storage"""
        if not self.enabled:
            return False

        try:
            self.s3.upload_fileobj(file_obj, self.bucket_name, object_name)
            return True
        except Exception as e:
            log.error(f"Error uploading file object to R2: {e}")
            return False

    def download_file(self, object_name: str, file_path: str) -> bool:
        """Download a file from R2 storage"""
        if not self.enabled:
            return False

        try:
            self.s3.download_file(self.bucket_name, object_name, file_path)
            return True
        except Exception as e:
            log.error(f"Error downloading file from R2: {e}")
            return False

    def get_presigned_url(self, object_name: str, expiration: int = 1800) -> Optional[str]:
        """Generate a presigned URL for object download"""
        if not self.enabled:
            return None

        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_name
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            log.error(f"Error generating presigned URL: {e}")
            return None

    def delete_file(self, object_name: str) -> bool:
        """Delete a file from R2 storage"""
        if not self.enabled:
            return False

        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except Exception as e:
            log.error(f"Error deleting file from R2: {e}")
            return False 