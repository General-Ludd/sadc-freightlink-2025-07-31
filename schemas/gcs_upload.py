from pydantic import BaseModel

class UploadRequest(BaseModel):
    file_name: str
    content_type: str

class UploadResponse(BaseModel):
    upload_url: str
    public_url: str
