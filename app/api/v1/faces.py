"""Simple face search API endpoint"""

from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, status, Query
from fastapi.responses import JSONResponse

from app.middleware.correlation_id import get_correlation_id
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
):
    """Search for similar faces using provider-specific distance matching"""
    
    # Read image data
    image_data = await image.read()
    
    # Search similar faces - let global error handler catch exceptions
    return dedup_service.search_similar_faces(
        image_data=image_data,
        filename=image.filename or "image.jpg",
        limit=limit,
        sentra_id=sentra_id,
        distance=distance
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
):
    """Validate whether a face is a duplicate of an existing enrollment"""
    image_data = await image.read()

    result = dedup_service.validate_face(
        image_data=image_data,
        filename=image.filename or "image.jpg",
        limit=limit,
        sentra_id=sentra_id,
        distance=distance,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseFormatter.success(
            data=result.model_dump(by_alias=True),
            correlation_id=get_correlation_id(),
        ),
    )