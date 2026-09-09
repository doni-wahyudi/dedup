"""Application settings and configuration management for Dedup Service"""

from typing import Literal, Optional
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application Settings
    app_name: str = Field(default="dedup-service", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # API Settings
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 prefix")
    max_upload_size: int = Field(default=10485760, description="Max upload size in bytes (10MB)")
    
    # CORS Settings
    cors_origins: str = Field(default="*", description="CORS allowed origins (comma-separated)")
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Convert CORS origins string to list"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    # SQL Server Database Settings
    db_server: str = Field(default="localhost", description="SQL Server host")
    db_port: int = Field(default=1433, description="SQL Server port")
    db_name: str = Field(default="enrollment_db", description="Database name")
    db_schema: str = Field(default="enrollment", description="Database schema")
    db_username: str = Field(default="sa", description="Database username")
    db_password: str = Field(default="", description="Database password - MUST be set via environment variable")
    db_driver: str = Field(default="pymssql", description="Database driver")
    db_pool_size: int = Field(default=10, description="Database connection pool size")
    db_pool_recycle: int = Field(default=3600, description="Connection pool recycle time (seconds)")
    db_echo: bool = Field(default=False, description="SQLAlchemy echo SQL queries")
    
    @property
    def database_url(self) -> str:
        """Generate SQLAlchemy database URL with URL-encoded credentials"""
        username = quote_plus(self.db_username)
        password = quote_plus(self.db_password)
        return f"mssql+{self.db_driver}://{username}:{password}@{self.db_server}:{self.db_port}/{self.db_name}"
    
    # Milvus Settings
    milvus_host: str = Field(default="localhost", description="Milvus host")
    milvus_port: int = Field(default=19530, description="Milvus port")
    milvus_user: str = Field(default="devuser", description="Milvus username")
    milvus_password: str = Field(default="", description="Milvus password - MUST be set via environment variable")
    milvus_collection: str = Field(
        default="enrollment_embeddings",
        description="Milvus collection name"
    )
    milvus_search_timeout: float = Field(
        default=10.0,
        description="Milvus search timeout in seconds"
    )
    
    # Milvus Index Settings - insightface provider (HNSW + IP)
    milvus_insightface_index_type: str = Field(
        default="HNSW",
        description="Milvus index type for insightface (HNSW recommended)"
    )
    milvus_insightface_metric_type: str = Field(
        default="IP",
        description="Milvus metric type for insightface (IP = Inner Product)"
    )
    milvus_insightface_hnsw_m: int = Field(
        default=16,
        description="HNSW M parameter (number of bi-directional links)"
    )
    milvus_insightface_hnsw_ef_construction: int = Field(
        default=200,
        description="HNSW ef_construction parameter (larger = better recall, slower build)"
    )
    
    # Face Recognition Settings
    face_recognition_provider: Literal["insightface"] = Field(
        default="insightface",
        description="Face recognition provider (only insightface supported)"
    )
    face_detection_threshold: float = Field(
        default=0.6,
        description="Face detection confidence threshold"
    )
    image_max_size: int = Field(
        default=1920,
        description="Maximum image dimension for processing"
    )
    allow_multiple_faces: bool = Field(
        default=False,
        description="Allow multiple faces in image (select largest if true, reject if false)"
    )
    image_formats: str = Field(
        default="JPEG,JPG,PNG",
        description="Supported image formats (comma-separated)"
    )
    image_extensions: str = Field(
        default=".jpg,.jpeg,.png",
        description="Supported image extensions (comma-separated)"
    )
    
    # Face 1:1 Comparison Settings
    face_compare_threshold: float = Field(
        default=0.4,
        description="Similarity threshold for 1:1 face comparison (cosine similarity, 0.0-1.0)"
    )
    
    # Image Quality Validation Settings
    quality_validation_enabled: bool = Field(
        default=True,
        description="Enable image quality validation before face comparison/search"
    )
    quality_min_image_width: int = Field(
        default=200,
        description="Minimum required image width in pixels"
    )
    quality_min_image_height: int = Field(
        default=200,
        description="Minimum required image height in pixels"
    )
    quality_min_face_size: int = Field(
        default=80,
        description="Minimum face bounding box width/height in pixels"
    )
    quality_blur_threshold: float = Field(
        default=100.0,
        description="Minimum Laplacian variance threshold for blur detection (higher = sharper)"
    )
    quality_lighting_min: float = Field(
        default=40.0,
        description="Minimum mean brightness (0-255, below this is underexposed/too dark)"
    )
    quality_lighting_max: float = Field(
        default=220.0,
        description="Maximum mean brightness (0-255, above this is overexposed/too bright)"
    )
    quality_boundary_margin: int = Field(
        default=5,
        description="Minimum margin in pixels from image boundary to ensure face is not cut off"
    )
    
    @property
    def image_formats_set(self) -> set[str]:
        """Convert image formats string to set"""
        return {fmt.strip().upper() for fmt in self.image_formats.split(",")}
    
    @property
    def image_extensions_set(self) -> set[str]:
        """Convert image extensions string to set"""
        return {ext.strip().lower() for ext in self.image_extensions.split(",")}
    
    # Search Defaults
    default_top_k: int = Field(
        default=10,
        description="Default Top-K for search"
    )
    default_threshold: float = Field(
        default=0.6,
        description="Default L2 distance threshold (0.0-1.0, lower is better, <0.6 same person)"
    )
    max_top_k: int = Field(
        default=100,
        description="Maximum allowed Top-K"
    )
    
    # Validation
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper
    
    @field_validator("max_upload_size")
    @classmethod
    def validate_max_upload_size(cls, v: int) -> int:
        """Validate max upload size"""
        if v <= 0:
            raise ValueError("max_upload_size must be greater than 0")
        return v
    
    @field_validator("default_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold"""
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        return v
    
    # Fraud Detection Scheduler Settings
    fraud_detector_enabled: bool = Field(default=True, description="Enable fraud detection scheduler")
    fraud_detector_interval_seconds: int = Field(default=60, description="Fraud detection interval in seconds")
    fraud_detector_batch_size: int = Field(default=1000, description="Batch size for fraud detection")
    fraud_detector_threshold: float = Field(default=0.7, description="IP distance threshold for fraud detection")
    fraud_detector_top_k: int = Field(default=5, description="Top K results from Milvus search")
    
    # Scheduler Distribution (for multiple concurrent schedulers via modulo)
    fraud_detector_scheduler_id: Optional[int] = Field(default=None, description="Scheduler ID (0-indexed) for multi-instance")
    fraud_detector_total_schedulers: Optional[int] = Field(default=None, description="Total number of scheduler instances")


# Global settings instance
settings = Settings()
