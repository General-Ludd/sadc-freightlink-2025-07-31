from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, FastAPI
from sqlalchemy.orm import Session
from db.database import SessionLocal
from pydantic import BaseModel
from google.cloud import storage
import datetime
import os
import uuid
import re
from schemas.gcs_upload import UploadRequest

# Load your service account credentials
# Build the path relative to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
key_path = os.path.join(BASE_DIR, "secrets", "sadc-freightlink-4b7604ef086c.json")

# Set the environment variable
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

router = APIRouter()

def sanitize_filename(filename: str) -> str:
    """
    Cleans up file names by replacing unsafe characters,
    keeping only alphanumeric, underscore, hyphen, and dot.
    """
    # Separate name and extension
    name, ext = os.path.splitext(filename)
    ext = ext.lower().lstrip('.')  # remove the dot for safety

    # Replace spaces and unsafe characters with "_"
    safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', name)

    # Add a UUID to avoid overwrites
    return f"{uuid.uuid4()}_{safe_name}.{ext}"

@router.post("/generate-upload-url")
async def generate_upload_url(data: UploadRequest):
    bucket_name = "freightlink-docs-images-bucket"

    # Sanitize filename
    safe_filename = sanitize_filename(data.file_name)

    storage_client = storage.Client()
    bucket = storage_client.bucket("freightlink-docs-images-bucket")
    blob = bucket.blob(safe_filename)

    # Create signed URL valid for 15 minutes
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="PUT",
        content_type=data.content_type
    )

    public_url = f"https://storage.googleapis.com/{bucket_name}/{safe_filename}"

    return {
        "upload_url": upload_url,
        "public_url": public_url
    }