"""Milvus vector database client for face similarity search (Read-only)"""

from typing import Optional, List, Dict

import structlog
from pymilvus import (
    Collection,
    connections,
    utility,
    MilvusClient as PyMilvusClient,
)

from app.config.settings import settings
from app.utils.exceptions import DatabaseError

logger = structlog.get_logger(__name__)


class MilvusClient:
    """Client for Milvus vector database operations (Search only)"""

    def __init__(self):
        self.host = settings.milvus_host
        self.port = settings.milvus_port
        self.user = settings.milvus_user
        self.password = settings.milvus_password
        self.collection_name = settings.milvus_collection
        self.collection: Optional[Collection] = None
        self._connected = False
        self.metric_type = settings.milvus_insightface_metric_type
        self.index_type = settings.milvus_insightface_index_type
        self.py_client: Optional[PyMilvusClient] = None

    def connect(self) -> None:
        """Establish connection to Milvus"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
            )
            self._connected = True

            # Initialize PyMilvusClient for get operations
            uri = f"http://{self.host}:{self.port}"
            token = f"{self.user}:{self.password}"
            self.py_client = PyMilvusClient(uri=uri, token=token)

            logger.info(
                "connected_to_milvus",
                host=self.host,
                port=self.port,
                user=self.user
            )
        except Exception as e:
            logger.error("milvus_connection_failed", error=str(e))
            raise DatabaseError(
                message=f"Failed to connect to Milvus: {str(e)}",
                details={"host": self.host, "port": self.port}
            )

    def disconnect(self) -> None:
        """Disconnect from Milvus"""
        try:
            if self._connected:
                connections.disconnect(alias="default")
                self._connected = False
                logger.info("disconnected_from_milvus")
        except Exception as e:
            logger.warning("milvus_disconnect_warning", error=str(e))

    def init_collection(self) -> None:
        """Initialize collection - load existing collection (Read-only)"""
        try:
            if self.collection_name in utility.list_collections():
                logger.info("collection_exists", collection=self.collection_name)
                self.collection = Collection(self.collection_name)
                self.collection.load()
                logger.info("collection_loaded", collection=self.collection_name)
            else:
                raise DatabaseError(
                    message=f"Collection '{self.collection_name}' not found. Please run enrollment service first.",
                    details={"collection_name": self.collection_name}
                )
        except Exception as e:
            logger.error("collection_initialization_failed", error=str(e))
            raise DatabaseError(
                message=f"Failed to initialize collection: {str(e)}",
                details={"collection_name": self.collection_name}
            )

    def batch_search_similar_faces(
            self,
            query_vectors: List[List[float]],
            limit: int = 10,
            sentra_id: Optional[str] = None,
            distance: Optional[float] = None
    ) -> List[List[Dict]]:
        """Batch search for similar faces using multiple query vectors
        
        Args:
            query_vectors: List of face embedding vectors (each 128 dimensions)
            limit: Maximum number of results per query
            sentra_id: Optional Sentra ID filter
            distance: Optional distance filter
                     For L2: include if distance <= value
                     For IP: include if distance >= value
        
        Returns:
            List of match lists, one per input query vector
            Each match list contains dictionaries with face data
        """
        try:
            if self.collection is None:
                raise DatabaseError("Collection not initialized")

            if not query_vectors:
                return []

            # Build filter expression
            filter_expr = None
            if sentra_id:
                filter_expr = f'sentra_id == "{sentra_id}"'

            # Get search parameters directly from settings
            search_params = {
                "metric_type": self.metric_type,
                "params": {"ef": 64}  # HNSW search parameter
            }

            # Log search parameters for debugging
            logger.debug(
                "batch_search_params",
                query_count=len(query_vectors),
                limit=limit,
                metric_type=self.metric_type,
                index_type=self.index_type,
                search_params=search_params
            )

            # Execute batch search
            results = self.collection.search(
                data=query_vectors,
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=filter_expr,
                output_fields=["id", "nik", "cif_name", "cif_code", "sentra_id", "sentra_name", "mms_code", "mms_name",
                               "co_assignment_nik", "co_assignment_code", "co_assignment_name", "co_enrol_nik",
                               "co_enrol_code", "co_enrol_name", "enroll_date_time", "image_url", "created_at"]
            )

            # Process results for each query
            all_matches = []
            for query_idx, hits in enumerate(results):
                matches = []
                for hit in hits:
                    hit_distance = float(hit.distance)

                    # Apply distance filtering if specified (IP: higher = more similar)
                    if distance is not None:
                        if hit_distance < distance:  # For IP metric
                            continue

                    match = {
                        "id": hit.id,
                        "nik": hit.entity.get("nik"),
                        "cif_name": hit.entity.get("cif_name"),
                        "cif_code": hit.entity.get("cif_code"),
                        "sentra_id": hit.entity.get("sentra_id"),
                        "sentra_name": hit.entity.get("sentra_name"),
                        "mms_code": hit.entity.get("mms_code"),
                        "mms_name": hit.entity.get("mms_name"),
                        "co_assignment_nik": hit.entity.get("co_assignment_nik"),
                        "co_assignment_code": hit.entity.get("co_assignment_code"),
                        "co_assignment_name": hit.entity.get("co_assignment_name"),
                        "co_enrol_nik": hit.entity.get("co_enrol_nik"),
                        "co_enrol_code": hit.entity.get("co_enrol_code"),
                        "co_enrol_name": hit.entity.get("co_enrol_name"),
                        "enroll_date_time": hit.entity.get("enroll_date_time"),
                        "image_url": hit.entity.get("image_url"),
                        "distance": hit_distance,
                        "created_at": hit.entity.get("created_at")
                    }
                    matches.append(match)

                all_matches.append(matches)

                # Log per-query results for clarity
                logger.debug(
                    "query_results_processed",
                    query_index=query_idx,
                    query_vector_length=len(query_vectors[query_idx]),
                    results_count=len(matches),
                    top_result_id=matches[0]["id"] if matches else None
                )

            logger.info(
                "batch_search_completed",
                queries=len(query_vectors),
                total_results=sum(len(matches) for matches in all_matches),
                distance_filter_applied=distance is not None,
                distance_filter=distance
            )

            return all_matches

        except Exception as e:
            logger.error("batch_search_failed",
                         query_count=len(query_vectors),
                         error=str(e))
            raise DatabaseError(
                message=f"Failed to batch search similar faces: {str(e)}",
                details={"query_count": len(query_vectors), "limit": limit}
            )

    def search_similar_faces(
            self,
            query_vector: list[float],
            limit: int = 10,
            sentra_id: Optional[str] = None,
            distance: Optional[float] = None
    ) -> List[Dict]:
        """Search for similar faces using provider-specific parameters
        
        Args:
            query_vector: Face embedding vector (128 dimensions)
            limit: Maximum number of results
            sentra_id: Optional Sentra ID filter
            distance: Optional distance filter
                     For L2: include if distance <= value
                     For IP: include if distance >= value
        
        Returns:
            List of matches sorted by distance, filtered if specified
        """
        try:
            if self.collection is None:
                raise DatabaseError("Collection not initialized")

            # Build filter expression
            filter_expr = None
            if sentra_id:
                filter_expr = f'sentra_id == "{sentra_id}"'

            # Get search parameters directly from settings
            search_params = {
                "metric_type": self.metric_type,
                "params": {"ef": 64}  # HNSW search parameter
            }

            # Log search parameters for debugging
            logger.debug(
                "search_params",
                metric_type=self.metric_type,
                index_type=self.index_type,
                ef=64,
                limit=limit
            )

            # Execute search
            results = self.collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=filter_expr,
                output_fields=["id", "nik", "cif_name", "cif_code", "sentra_id", "sentra_name", "mms_code", "mms_name",
                               "co_assignment_nik", "co_assignment_code", "co_assignment_name", "co_enrol_nik",
                               "co_enrol_code", "co_enrol_name", "enroll_date_time", "image_url", "created_at",
                               "embedding"],
                timeout=settings.milvus_search_timeout
            )

            # Process results
            matches = []
            for hits in results:
                for hit in hits:
                    hit_distance = float(hit.distance)

                    # Apply distance filtering if specified (IP: higher = more similar)
                    if distance is not None:
                        if hit_distance < distance:  # For IP metric
                            continue

                    match = {
                        "id": hit.id,
                        "nik": hit.entity.get("nik"),
                        "cif_name": hit.entity.get("cif_name"),
                        "cif_code": hit.entity.get("cif_code"),
                        "sentra_id": hit.entity.get("sentra_id"),
                        "sentra_name": hit.entity.get("sentra_name"),
                        "mms_code": hit.entity.get("mms_code"),
                        "mms_name": hit.entity.get("mms_name"),
                        "co_assignment_nik": hit.entity.get("co_assignment_nik"),
                        "co_assignment_code": hit.entity.get("co_assignment_code"),
                        "co_assignment_name": hit.entity.get("co_assignment_name"),
                        "co_enrol_nik": hit.entity.get("co_enrol_nik"),
                        "co_enrol_code": hit.entity.get("co_enrol_code"),
                        "co_enrol_name": hit.entity.get("co_enrol_name"),
                        "enroll_date_time": hit.entity.get("enroll_date_time"),
                        "image_url": hit.entity.get("image_url"),
                        "embedding": hit.entity.get("embedding"),
                        "distance": hit_distance,
                        "created_at": hit.entity.get("created_at")
                    }
                    matches.append(match)

            logger.info("milvus_search_completed",
                        total_results=len(matches),
                        distance_filter_applied=distance is not None,
                        distance_filter=distance)
            return matches

        except Exception as e:
            logger.error("search_failed", error=str(e))
            raise DatabaseError(
                message=f"Failed to search similar faces: {str(e)}",
                details={"limit": limit}
            )

    def get_stats(self) -> dict:
        """Get collection statistics"""
        try:
            if self.collection is None:
                raise DatabaseError("Collection not initialized")

            self.collection.flush()
            stats = {
                "collection_name": self.collection_name,
                "total_enrollments": self.collection.num_entities,
                "metric_type": self.metric_type,
                "index_type": self.index_type,
            }

            return stats

        except Exception as e:
            logger.error("get_stats_failed", error=str(e))
            raise DatabaseError(f"Failed to get stats: {str(e)}")

    def get_by_ids(
            self,
            ids: List[str],
            output_fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """Get faces by multiple Milvus IDs
        
        Args:
            ids: List of Milvus IDs to retrieve
            output_fields: Optional list of fields to return. If None, returns all fields.
        
        Returns:
            List of face data dictionaries
        """
        try:
            if self.py_client is None:
                raise DatabaseError("PyMilvus client not initialized")

            if not ids:
                return []

            # Default output fields
            if output_fields is None:
                output_fields = ["id", "nik", "cif_code", "sentra_id", "mms_id", "image_url", "embedding", "created_at"]

            # Get data from Milvus using PyMilvusClient (recommended API)
            res = self.py_client.get(
                collection_name=self.collection_name,
                ids=ids,
                output_fields=output_fields
            )

            logger.info(
                "get_by_ids_completed",
                requested_ids=len(ids),
                returned_records=len(res)
            )

            return res

        except Exception as e:
            logger.error("get_by_ids_failed", error=str(e), ids=ids)
            raise DatabaseError(
                message=f"Failed to get faces by IDs: {str(e)}",
                details={"ids": ids}
            )

    def health_check(self) -> bool:
        """Check if Milvus is healthy"""
        try:
            return self._connected and self.collection is not None
        except Exception:
            return False


# Global instance
milvus_client = MilvusClient()
