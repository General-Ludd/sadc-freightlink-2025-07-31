from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from google.cloud import storage
from google.oauth2 import service_account
import datetime
import os
import uuid
import re
import json
import logging
from schemas.gcs_upload import UploadRequest

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)

def sanitize_filename(filename: str) -> str:
    """
    Cleans up file names by replacing unsafe characters,
    keeping only alphanumeric, underscore, hyphen, and dot.
    """
    name, ext = os.path.splitext(filename)
    ext = ext.lower().lstrip('.')  # remove the dot for safety
    safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', name)
    return f"{uuid.uuid4()}_{safe_name}.{ext}"

# Load credentials: environment variable (Render) or hardcoded (local)
gcs_key_json = os.environ.get("GCS_KEY_JSON")
if gcs_key_json:
    logging.info("Using Render environment variable for GCS credentials")
    credentials_info = json.loads(gcs_key_json)
else:
    logging.info("Using hardcoded credentials for local testing")
    credentials_info = {
        "type": "service_account",
        "project_id": "sadc-freightlink",
        "private_key_id": "4b7604ef086cda867901857bb55f60009153b7f8",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDl186ZO6ghiE8v\nv/F9Q9o79eYNVn2vIkXW4LtaG6ISIhKPjE2gxrhtGCNJJgX0Uz+MaBeI1Dl2Lx8v\n2/2XaEBrCv+AfN6joa9winTI3YzieFyFnvQHMe6VFnAKzPd12TdezylbyHyNxRWF\nAEPVBtfXstT3qHqUxl2G7cD75O7rL8t+8qoCfQTR+fooYhGgeOczG9SEJHRY4SJ6\nhJ3VttQRq/SOMSu6e47ANfpQ353DX1wQyJ5/VHp6KLEC9Ifflyz+OZ8qK2EUDgQW\nizTpZjCi784BbYCEV4UOOoyL8CIDDKg6aTEZCViT5VV5S1d0g2wbbA2wPaQhRCk/\nb0OM15qrAgMBAAECggEAZv9ZCUj3FKPJXIwG00wrSVBt2c9G/kr9AghuXLhiXf7f\n020bwm8a6WR2N4rvAyilIy3oUfxMjb4bGy7ZytZAe9ePXMxYVvqXLHcXU4YY4snu\nKEDteSXylOPbrLNiN3DyQ63RClzjGALYHGRcgWOSKQpuLldVK0NjWRpFL3xNZp2I\nih7u8rxfhogrkABaN/MJ8+hVfxNetYvM48VRidKR5XknsWHs5EzhL19SOBJMTK3O\nPagxAYnclIqWXL9CP/tkLczCWNPxMfe+KWVc2HRNCMzTaQ1FWhDWUE7wR83ni4ny\nRHkiHbMa+4NZOcGZ4+NgyfV34J+fL1hs1SA6+qDEoQKBgQD0bdyxh+OKLtTuDSgL\n/vgDf9yDnyjcYFv1FRBfsF8pfmeSIOT3Y6etMbVRpnXJ2O3Ao0jqZWHvX+uuE3f8\ne62XNrKDxJ9PfZUbP2TNnGF5/KfjtmDC/ozi+95fRm2DLyNr6jt09Gb/Xim0t+m0\notH/sAEL1A1Smj4xmFiD4ZHbSwKBgQDwuS5nPNwd6+/r+qBgmxBY8AOfwIInGguH\nv/n5OryoUlOLwwSTcA98oY634b9krAI08/3E5qnFGuY7YxehPuC23MjGH6PbUVBG\nYkC7BwwVaeEAqEC4Ng2BV9gRec8/ON+t5gEXSIYVJL/qH7z3GidWuq2FvHJJ/xMl\nSyStYeNCIQKBgQCWj8m+rVbSunA8xmvhn8fD2BHMHdD8lnpuZ/AzESA9HfjMQWjo\nnkEd5R2sUt4BXJdu7uWuRI7j9XDmRGXHZ6ORHocttYLwYwniw9Ti9i3xB1mfYasO\n0d+UvdLHW0l/4hxuj9TaAOYk7SrBf/v8YcL7Pb4XPCKMvCgNQqtbaSoAKwKBgQCL\nLzdCX/ERp+qoMdhrIx1XnycpRkC65RdHnVumnCya0kcWJ2NM8F0z/aGsdm2YgtAf\n1/eh0pDUs5HtQoVWKSn68TtxOrgeRiy5FXRB73gwJXEAVUheenpij+0RZbHL51GF\nldiJothL/1yrvUAgS9H1FqjgC661VDO4u3LwgQnKoQKBgHe8tqFC3IkKOVmN6MpZ\n8mMojOxdXzUFPF2T/bTZYrw4/KlrtBRhh/ikNWd5cGhEfQjIokfGr5gWtHbPq/kG\nRhD0QBXv7ZTHxh0QUFSBxhvI2yMCffAAVq0259a0DJjf58YOuAS7kH56vle8H5Fc\nqHUXsh9Mp0xDIguVxwY5NkyC\n-----END PRIVATE KEY-----\n",
        "client_email": "frontend-file-uploader@sadc-freightlink.iam.gserviceaccount.com",
        "client_id": "104584973099257539453",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/frontend-file-uploader%40sadc-freightlink.iam.gserviceaccount.com"
    }

credentials = service_account.Credentials.from_service_account_info(credentials_info)
storage_client = storage.Client(credentials=credentials, project=credentials.project_id)

@router.post("/generate-upload-url")
async def generate_upload_url(data: UploadRequest):
    bucket_name = "freightlink-docs-images-bucket"

    # Sanitize filename
    safe_filename = sanitize_filename(data.file_name)

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(safe_filename)

    # Create signed URL valid for 15 minutes
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="PUT",
        headers={"x-goog-content-sha256": "UNSIGNED-PAYLOAD"},  # 👈 crucial fix
    )

    public_url = f"https://storage.googleapis.com/{bucket_name}/{safe_filename}"

    return {
        "upload_url": upload_url,
        "public_url": public_url
    }
