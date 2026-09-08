"""API endpoints for fraud case management"""

from typing import List

import structlog
from fastapi import APIRouter, HTTPException, status

from app.database.repositories.enrollment import FraudCaseRepository
from app.database.specifications.criteria import Filter, QueryOperator
from app.models.schemas import FraudCaseSchema

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/fraud-cases", tags=["fraud"])
fraud_repo = FraudCaseRepository()


@router.get("/by-primary/{primary_enrollment_id}", response_model=List[FraudCaseSchema])
async def get_fraud_cases_by_primary(primary_enrollment_id: int):
    """
    Get fraud cases by primary enrollment ID with related enrollment data.
    
    **Parameters:**
    - `primary_enrollment_id`: The primary enrollment ID
    """
    try:
        filters = [
            Filter(field="primary_enrollment_id", operator=QueryOperator.EQUALS, value=primary_enrollment_id)
        ]

        cases = fraud_repo.get_by_specification(
            filters=filters,
            sorts=[("distance", False)],
            load_relationships=True
        )

        return [FraudCaseSchema.model_validate(case) for case in cases]
    except Exception as e:
        logger.error("get_fraud_cases_failed", primary_enrollment_id=primary_enrollment_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get fraud cases"
        )
