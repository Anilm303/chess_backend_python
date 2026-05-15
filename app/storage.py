import io
import os
from uuid import uuid4

UPLOAD_ROOT = 'uploads'


def _storage_mode():
    return os.getenv('MEDIA_STORAGE', 'local').strip().lower()


def _normalize_public_base_url():
    base = os.getenv('MEDIA_PUBLIC_BASE_URL', '').strip().rstrip('/')
    return base


def store_media_bytes(category, filename, data, content_type='application/octet-stream'):
    """Store media locally or in S3, depending on MEDIA_STORAGE."""
    mode = _storage_mode()
    category = category.strip('/').strip()
    if not category:
        category = 'misc'

    if mode == 's3':
        bucket = os.getenv('S3_BUCKET', '').strip()
        region = os.getenv('S3_REGION', '').strip()
        if not bucket or not region:
            raise RuntimeError('S3_BUCKET and S3_REGION are required when MEDIA_STORAGE=s3')

        import boto3

        key = f'{category}/{filename}'
        client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=os.getenv('S3_ACCESS_KEY_ID', '').strip() or None,
            aws_secret_access_key=os.getenv('S3_SECRET_ACCESS_KEY', '').strip() or None,
        )
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        # Keep a local copy so thumbnail generation and local debugging still work.
        folder = os.path.join(UPLOAD_ROOT, category)
        os.makedirs(folder, exist_ok=True)
        local_filepath = os.path.join(folder, filename)
        with open(local_filepath, 'wb') as file_handle:
            file_handle.write(data)

        public_base = _normalize_public_base_url()
        if public_base:
            return f'{public_base}/{key}'

        return f'https://{bucket}.s3.{region}.amazonaws.com/{key}'

    folder = os.path.join(UPLOAD_ROOT, category)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, 'wb') as file_handle:
        file_handle.write(data)
    return f'/uploads/{category}/{filename}'


def create_media_filename(extension):
    return f'{uuid4()}.{extension.lstrip(".")}'
