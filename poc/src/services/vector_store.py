"""
Vector store service for Milvus database operations.
"""

import os
from typing import List, Dict, Any, Optional
from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema
from pymilvus.exceptions import MilvusException
import logging
from datetime import datetime

from ..models.document import DocumentChunk

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Milvus vector database manager for document embeddings and semantic search.
    """
    
    def __init__(self, 
                 host: Optional[str] = None, 
                 token: Optional[str] = None,
                 collection_name: str = "pdf_documents"):
        """
        Initialize Milvus client and collection.
        
        Args:
            host: Milvus host URL (defaults to ZILLIZ_HOST env var)
            token: Milvus token (defaults to ZILLIZ_TOKEN env var)
            collection_name: Collection name for storing embeddings
        """
        self.host = host or os.getenv("ZILLIZ_HOST")
        self.token = token or os.getenv("ZILLIZ_TOKEN")
        self.collection_name = collection_name
        
        if not self.host or not self.token:
            raise ValueError("Milvus host and token must be provided")
            
        # Clean up host URL if needed
        if self.host and not self.host.startswith(('http://', 'https://')):
            self.host = f"https://{self.host}"
            
        logger.info(f"Connecting to Milvus at {self.host}")
        
        try:
            # Initialize Milvus client with updated parameters
            self.client = MilvusClient(
                uri=self.host,
                token=self.token,
                timeout=60.0,  # Increased timeout
                db_name="default"  # Specify default database
            )
            self.embedding_dim = 1536  # OpenAI text-embedding-ada-002 dimension
            
            # Test connection
            logger.info("Testing Milvus connection...")
            self._test_connection()
            
            # Initialize collection
            self._ensure_collection_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Milvus client: {e}")
            logger.error(f"Host: {self.host}")
            logger.error(f"Token provided: {'Yes' if self.token else 'No'}")
            raise ValueError(f"Milvus client initialization failed: {e}")
    
    def _test_connection(self) -> None:
        """Test Milvus connection."""
        try:
            # Try to list collections to test connection
            collections = self.client.list_collections()
            logger.info(f"Successfully connected to Milvus. Found {len(collections)} collections.")
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise
        
    def _ensure_collection_exists(self) -> None:
        """Ensure the collection exists with proper schema."""
        try:
            # Check if collection exists
            if self.client.has_collection(self.collection_name):
                logger.info(f"Collection '{self.collection_name}' already exists")
                return
                
            # Use the simplified create_collection method with error handling
            try:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    dimension=self.embedding_dim,
                    metric_type="COSINE",
                    id_type="string",
                    max_length=100,  # for primary key
                    consistency_level="Strong"
                )
            except Exception as create_error:
                logger.error(f"Failed to create collection with simplified method: {create_error}")
                # Fallback: try with basic parameters
                self.client.create_collection(
                    collection_name=self.collection_name,
                    dimension=self.embedding_dim
                )
            
            logger.info(f"Created collection '{self.collection_name}' successfully")
            
        except MilvusException as e:
            logger.error(f"Failed to create collection: {e}")
            raise
            
    def _create_collection_schema(self) -> CollectionSchema:
        """Create collection schema for document chunks."""
        fields = [
            FieldSchema(
                name="chunk_id",
                dtype=DataType.VARCHAR,
                max_length=100,
                is_primary=True,
                description="Unique chunk identifier"
            ),
            FieldSchema(
                name="document_id", 
                dtype=DataType.VARCHAR,
                max_length=100,
                description="Document identifier"
            ),
            FieldSchema(
                name="content",
                dtype=DataType.VARCHAR,
                max_length=8192,
                description="Text content of the chunk"
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.embedding_dim,
                description="Embedding vector"
            ),
            FieldSchema(
                name="page_number",
                dtype=DataType.INT32,
                description="Page number in document"
            ),
            FieldSchema(
                name="chunk_index",
                dtype=DataType.INT32,
                description="Chunk index in document"
            ),
            FieldSchema(
                name="keywords",
                dtype=DataType.VARCHAR,
                max_length=1000,
                description="Comma-separated keywords"
            ),
            FieldSchema(
                name="importance_score",
                dtype=DataType.FLOAT,
                description="Chunk importance score"
            ),
            FieldSchema(
                name="created_at",
                dtype=DataType.VARCHAR,
                max_length=50,
                description="Creation timestamp"
            )
        ]
        
        return CollectionSchema(
            fields=fields,
            description="Document chunks with embeddings for semantic search"
        )
        
    def _create_index(self) -> None:
        """Create vector index for efficient similarity search."""
        # Index is automatically created with the simplified create_collection method
        logger.info("Index created automatically with collection")
            
    def insert_document_chunks(self, chunks: List[DocumentChunk]) -> bool:
        """
        Insert document chunks with embeddings into the vector store.
        
        Args:
            chunks: List of DocumentChunk objects with embeddings
            
        Returns:
            bool: Success status
        """
        if not chunks:
            logger.warning("No chunks provided for insertion")
            return False
            
        try:
            # Prepare data for insertion (simplified format)
            data = []
            for chunk in chunks:
                if not chunk.embedding_vector:
                    logger.warning(f"Chunk {chunk.id} has no embedding vector, skipping")
                    continue
                    
                # Use simplified data format for auto-schema collection
                data.append({
                    "id": chunk.id,  # Primary key
                    "vector": chunk.embedding_vector,  # Vector field
                    "document_id": chunk.document_id,
                    "content": chunk.content[:8192],  # Truncate if too long
                    "page_number": chunk.page_number or 0,
                    "chunk_index": chunk.chunk_index,
                    "keywords": ",".join(chunk.keywords),
                    "importance_score": chunk.importance_score,
                    "created_at": chunk.created_at.isoformat()
                })
                
            if not data:
                logger.warning("No valid chunks with embeddings found")
                return False
                
            # Insert data
            self.client.insert(
                collection_name=self.collection_name,
                data=data
            )
            
            logger.info(f"Inserted {len(data)} chunks successfully")
            return True
            
        except MilvusException as e:
            logger.error(f"Failed to insert chunks: {e}")
            return False
            
    def search_similar_chunks(self, 
                            query_embedding: List[float],
                            top_k: int = 5,
                            score_threshold: float = 0.7,
                            document_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using semantic similarity.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of top results to return
            score_threshold: Minimum similarity score threshold
            document_ids: Optional filter by document IDs
            
        Returns:
            List of similar chunks with metadata
        """
        try:
            # Prepare search parameters
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # Build filter expression if document_ids provided
            filter_expr = None
            if document_ids:
                doc_filter = " or ".join([f'document_id == "{doc_id}"' for doc_id in document_ids])
                filter_expr = f"({doc_filter})"
                
            # Perform vector search
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_embedding],
                search_params=search_params,
                limit=top_k,
                filter=filter_expr,
                output_fields=[
                    "id", "document_id", "content", "page_number", 
                    "chunk_index", "keywords", "importance_score", "created_at"
                ]
            )
            
            # Process results
            similar_chunks = []
            if results and len(results) > 0:
                for hit in results[0]:
                    # Filter by score threshold
                    if hit.score < score_threshold:
                        continue
                        
                    chunk_data = {
                        "chunk_id": hit.entity.get("id"),
                        "document_id": hit.entity.get("document_id"),
                        "content": hit.entity.get("content"),
                        "page_number": hit.entity.get("page_number"),
                        "chunk_index": hit.entity.get("chunk_index"),
                        "keywords": hit.entity.get("keywords", "").split(",") if hit.entity.get("keywords") else [],
                        "importance_score": hit.entity.get("importance_score", 0.0),
                        "similarity_score": float(hit.score),
                        "created_at": hit.entity.get("created_at")
                    }
                    similar_chunks.append(chunk_data)
                    
            logger.info(f"Found {len(similar_chunks)} similar chunks above threshold {score_threshold}")
            return similar_chunks
            
        except MilvusException as e:
            logger.error(f"Failed to search similar chunks: {e}")
            return []
            
    def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a specific document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of document chunks
        """
        try:
            results = self.client.query(
                collection_name=self.collection_name,
                filter=f'document_id == "{document_id}"',
                output_fields=[
                    "id", "document_id", "content", "page_number",
                    "chunk_index", "keywords", "importance_score", "created_at"
                ]
            )
            
            chunks = []
            for result in results:
                chunk_data = {
                    "chunk_id": result.get("id"),
                    "document_id": result.get("document_id"),
                    "content": result.get("content"),
                    "page_number": result.get("page_number"),
                    "chunk_index": result.get("chunk_index"),
                    "keywords": result.get("keywords", "").split(",") if result.get("keywords") else [],
                    "importance_score": result.get("importance_score", 0.0),
                    "created_at": result.get("created_at")
                }
                chunks.append(chunk_data)
                
            # Sort by chunk_index
            chunks.sort(key=lambda x: x["chunk_index"])
            
            logger.info(f"Retrieved {len(chunks)} chunks for document {document_id}")
            return chunks
            
        except MilvusException as e:
            logger.error(f"Failed to get document chunks: {e}")
            return []
            
    def delete_document_chunks(self, document_id: str) -> bool:
        """
        Delete all chunks for a specific document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            bool: Success status
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                filter=f'document_id == "{document_id}"'
            )
            
            logger.info(f"Deleted chunks for document {document_id}")
            return True
            
        except MilvusException as e:
            logger.error(f"Failed to delete document chunks: {e}")
            return False
            
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            # Get collection info
            collection_info = self.client.describe_collection(self.collection_name)
            
            return {
                "collection_name": self.collection_name,
                "total_entities": collection_info.get("num_entities", 0),
                "index_status": "auto_index",
                "last_updated": datetime.now().isoformat()
            }
            
        except MilvusException as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "collection_name": self.collection_name,
                "total_entities": 0,
                "index_status": "unknown",
                "error": str(e)
            }
            
    def health_check(self) -> bool:
        """
        Check if the vector store is healthy and accessible.
        
        Returns:
            bool: Health status
        """
        try:
            # Check if collection exists and is accessible
            has_collection = self.client.has_collection(self.collection_name)
            
            if has_collection:
                # Try to describe the collection
                self.client.describe_collection(self.collection_name)
                
            logger.info("Vector store health check passed")
            return True
            
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return False