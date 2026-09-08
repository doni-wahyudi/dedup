"""Simple face search API endpoint"""

from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, status, Query, Header
from fastapi.responses import JSONResponse

from app.middleware.correlation_id import get_correlation_id, get_source_channel
from app.models.schemas import FaceSearchResponse
from app.services.dedup_service import dedup_service
from app.utils.response import ResponseFormatter

router = APIRouter(prefix="/faces", tags=["faces"])


@router.post(
    "/search",
    response_model=FaceSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search for similar faces",
    description="Find similar faces using provider-specific distance matching with optional similarity threshold",
)
async def search_faces(
    image: UploadFile = File(..., description="Face image file (JPG, PNG)"),
    limit: int = Query(
        default=10,
        ge=1, le=50,
        description="Maximum number of results to return"
    ),
    sentra_id: Optional[str] = Query(
        default=None, 
        description="Filter results by specific Sentra ID"
    ),
    distance: Optional[float] = Query(
        default=None,
        ge=0.0, le=1.0,
        description="Distance filter. L2: max distance, IP: min distance"
    ),
    x_channel: Optional[str] = Header(
        default=None,
        alias="X-Channel",
        description="Source channel (e.g. MMS, MOBILE, WEB)",
    ),
    x_source_channel: Optional[str] = Header(
        default=None,
        alias="X-Source-Channel",
        description="Alternative source channel header",
    ),
):
    """Search for similar faces using provider-specific distance matching"""
    channel = x_channel or x_source_channel or get_source_channel() or None
    
    # Read image data
    image_data = await image.read()
    
    # Search similar faces - let global error handler catch exceptions
    return dedup_service.search_similar_faces(
        image_data=image_data,
        filename=image.filename or "image.jpg",
        limit=limit,
        sentra_id=sentra_id,
        distance=distance,
        channel=channel,
    )


@router.post(
    "/validate",
    status_code=status.HTTP_200_OK,
    summary="Validate face for duplicates",
    description="Check whether a face already exists in the database above the specified similarity threshold",
)
async def validate_face(
    image: UploadFile = File(..., description="Face image file (JPG, PNG)"),
    limit: int = Form(
        default=10,
        ge=1, le=50,
        description="Maximum number of candidates to check"
    ),
    sentra_id: Optional[str] = Form(
        default=None,
        description="Filter by specific Sentra ID"
    ),
    distance: Optional[float] = Form(
        default=None,
        ge=0.0, le=1.0,
        description="Minimum similarity threshold (IP metric). Uses server default if not provided"
    ),
    x_channel: Optional[str] = Header(
        default=None,
        alias="X-Channel",
        description="Source channel (e.g. MMS, MOBILE, WEB)",
    ),
    x_source_channel: Optional[str] = Header(
        default=None,
        alias="X-Source-Channel",
        description="Alternative source channel header",
    ),
):
    """Validate whether a face is a duplicate of an existing enrollment"""
    channel = x_channel or x_source_channel or get_source_channel() or None
    image_data = await image.read()

    result = dedup_service.validate_face(
        image_data=image_data,
        filename=image.filename or "image.jpg",
        limit=limit,
        sentra_id=sentra_id,
        distance=distance,
        channel=channel,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseFormatter.success(
            data=result.model_dump(by_alias=True),
            correlation_id=get_correlation_id(),
            channel=channel,
        ),
    )


@router.post(
    "/compare",
    status_code=status.HTTP_200_OK,
    summary="Compare two face images",
    description="Perform 1:1 face comparison between two uploaded images. "
    "Returns Match/No Match status with similarity score.",
)
async def compare_faces(
    image1: UploadFile = File(..., description="First face image file (JPG, PNG)"),
    image2: UploadFile = File(..., description="Second face image file (JPG, PNG)"),
    threshold: Optional[float] = Form(
        default=None,
        ge=0.0,
        le=1.0,
        description="Similarity threshold (0.0-1.0). Uses server default if not provided",
    ),
    x_channel: Optional[str] = Header(
        default=None,
        alias="X-Channel",
        description="Source channel (e.g. MMS, MOBILE, WEB)",
    ),
    x_source_channel: Optional[str] = Header(
        default=None,
        alias="X-Source-Channel",
        description="Alternative source channel header",
    ),
):
    """Compare two face images and return similarity result (synchronous 1:1 comparison)"""
    channel = x_channel or x_source_channel or get_source_channel() or None
    image1_data = await image1.read()
    image2_data = await image2.read()

    result = dedup_service.compare_faces(
        image1_data=image1_data,
        image1_filename=image1.filename or "image1.jpg",
        image2_data=image2_data,
        image2_filename=image2.filename or "image2.jpg",
        threshold=threshold,
        channel=channel,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseFormatter.success(
            data=result.model_dump(),
            correlation_id=get_correlation_id(),
            channel=channel,
        ),
    )