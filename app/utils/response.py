"""Response formatter utilities for consistent API responses"""

import uuid
from datetime import datetime
from typing import Any, Optional, Dict

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Error detail object"""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = Field(True, description="Success flag")
    statusCode: int = Field(..., description="HTTP status code")
    data: Optional[Any] = Field(None, description="Response data")
    correlationId: Optional[str] = Field(None, description="Request correlation ID for tracing")
    channel: Optional[str] = Field(None, description="Source channel")


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = Field(False, description="Success flag")
    statusCode: int = Field(..., description="HTTP status code")
    error: ErrorDetail = Field(..., description="Error information")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    correlationId: str = Field(..., description="Request correlation ID for tracing")


class ResponseFormatter:
    """Helper class for formatting API responses"""

    @staticmethod
    def success(
        data: Any = None,
        status_code: int = 200,
        correlation_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format success response"""
        result = {
            "success": True,
            "statusCode": status_code,
            "data": data,
            "correlationId": correlation_id
        }
        if channel:
            result["channel"] = channel
        return result

    @staticmethod
    def error(
        error_code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format error response
        
        Args:
            error_code: Machine-readable error code
            message: Human-readable error message
            status_code: HTTP status code
            details: Additional error context
            timestamp: ISO 8601 timestamp (auto-generated if not provided)
            correlation_id: Request correlation ID for tracing (auto-generated if not provided)
            
        Returns:
            Formatted error response dict
        """
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat() + "Z"
        
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        return {
            "success": False,
            "statusCode": status_code,
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {}
            },
            "timestamp": timestamp,
            "correlationId": correlation_id
        }

    @staticmethod
    def created(
        data: Any = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format 201 created response"""
        return ResponseFormatter.success(data=data, status_code=201, correlation_id=correlation_id)

    @staticmethod
    def no_content(correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """Format 204 no content response"""
        return {
            "success": True,
            "statusCode": 204,
            "correlationId": correlation_id
        }
