"""API dependencies"""

import structlog
from fastapi import HTTPException, UploadFile, status

from app.config.settings import settings

logger = structlog.get_logger(__name__)


async def validate_image_upload(file: UploadFile) -> None:
    """Validate uploaded image file
    
    Args:
        file: Uploaded file
    
    Raises:
        HTTPException: If validation fails
    """
    # Check content type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": "File must be an image",
                "details": {"content_type": file.content_type}
            }
        )
    
    # Check file size (if available)
    if hasattr(file, "size") and file.size:
        if file.size > settings.max_upload_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "FILE_TOO_LARGE",
                    "message": "Image file is too large",
                    "details": {
                        "file_size_mb": round(file.size / (1024 * 1024), 2),
                        "max_size_mb": round(settings.max_upload_size / (1024 * 1024), 2)
                    }
                }
            )
