"""
Embedding service for text vectorization using OpenAI embeddings.
"""

import os
from typing import List, Optional, Dict, Any
import openai
from openai import OpenAI
import logging
import time
from datetime import datetime

from ..models.document import DocumentChunk
from ..models.question import Question

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings using OpenAI's text-embedding models.
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model: str = "text-embedding-ada-002",
                 max_retries: int = 3,
                 retry_delay: float = 1.0):
        """
        Initialize OpenAI embedding service.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model name
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided")
            
        self.client = OpenAI(api_key=self.api_key)
        
        # Model specifications
        self.model_specs = {
            "text-embedding-ada-002": {
                "max_tokens": 8191,
                "dimensions": 1536,
                "cost_per_1k_tokens": 0.0001
            },
            "text-embedding-3-small": {
                "max_tokens": 8191,
                "dimensions": 1536,
                "cost_per_1k_tokens": 0.00002
            },
            "text-embedding-3-large": {
                "max_tokens": 8191,
                "dimensions": 3072,
                "cost_per_1k_tokens": 0.00013
            }
        }
        
        if model not in self.model_specs:
            logger.warning(f"Unknown model {model}, using default specifications")
            
    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
            
        # Truncate text if too long
        max_tokens = self.model_specs.get(self.model, {}).get("max_tokens", 8191)
        if len(text.split()) > max_tokens:
            words = text.split()[:max_tokens]
            text = " ".join(words)
            logger.warning(f"Text truncated to {max_tokens} tokens")
            
        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=text,
                    encoding_format="float"
                )
                
                if response.data and len(response.data) > 0:
                    embedding = response.data[0].embedding
                    logger.debug(f"Generated embedding with {len(embedding)} dimensions")
                    return embedding
                else:
                    logger.error("No embedding data in response")
                    return None
                    
            except openai.RateLimitError as e:
                logger.warning(f"Rate limit exceeded (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                return None
                
            except openai.APIError as e:
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return None
                
            except Exception as e:
                logger.error(f"Unexpected error generating embedding: {e}")
                return None
                
        logger.error(f"Failed to generate embedding after {self.max_retries} attempts")
        return None
        
    def embed_texts(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch
            
        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        if not texts:
            return []
            
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1}")
            
            # Filter out empty texts
            valid_texts = [(idx, text) for idx, text in enumerate(batch_texts) if text and text.strip()]
            
            if not valid_texts:
                # Add None for all texts in this batch
                all_embeddings.extend([None] * len(batch_texts))
                continue
                
            for attempt in range(self.max_retries):
                try:
                    # Prepare texts for API call
                    input_texts = [text for _, text in valid_texts]
                    
                    response = self.client.embeddings.create(
                        model=self.model,
                        input=input_texts,
                        encoding_format="float"
                    )
                    
                    # Process response
                    batch_embeddings = [None] * len(batch_texts)
                    
                    for api_idx, (original_idx, _) in enumerate(valid_texts):
                        if api_idx < len(response.data):
                            batch_embeddings[original_idx] = response.data[api_idx].embedding
                            
                    all_embeddings.extend(batch_embeddings)
                    logger.debug(f"Generated {len([e for e in batch_embeddings if e is not None])} embeddings in batch")
                    break
                    
                except openai.RateLimitError as e:
                    logger.warning(f"Rate limit exceeded for batch (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                    # Add None for all texts in this batch
                    all_embeddings.extend([None] * len(batch_texts))
                    break
                    
                except Exception as e:
                    logger.error(f"Error processing batch (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    # Add None for all texts in this batch
                    all_embeddings.extend([None] * len(batch_texts))
                    break
                    
        logger.info(f"Generated {len([e for e in all_embeddings if e is not None])} embeddings out of {len(texts)} texts")
        return all_embeddings
        
    def embed_question(self, question: Question) -> Optional[List[float]]:
        """
        Generate embedding for a question.
        
        Args:
            question: Question object
            
        Returns:
            Embedding vector or None if failed
        """
        # Combine question content with keywords for better context
        text_to_embed = question.content
        
        if question.keywords:
            keywords_text = " ".join(question.keywords)
            text_to_embed = f"{question.content} {keywords_text}"
            
        return self.embed_text(text_to_embed)
        
    def embed_document_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Generate embeddings for document chunks and update them in-place.
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            List of DocumentChunk objects with embeddings
        """
        if not chunks:
            return []
            
        logger.info(f"Generating embeddings for {len(chunks)} document chunks")
        
        # Extract texts from chunks
        texts = []
        for chunk in chunks:
            # Combine content with keywords for better context
            text = chunk.content
            if chunk.keywords:
                keywords_text = " ".join(chunk.keywords)
                text = f"{chunk.content} {keywords_text}"
            texts.append(text)
            
        # Generate embeddings
        embeddings = self.embed_texts(texts)
        
        # Update chunks with embeddings
        updated_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            if embedding is not None:
                chunk.embedding_vector = embedding
                chunk.embedding_model = self.model
                chunk.updated_at = datetime.now()
                updated_chunks.append(chunk)
            else:
                logger.warning(f"Failed to generate embedding for chunk {chunk.id}")
                
        logger.info(f"Successfully generated embeddings for {len(updated_chunks)} chunks")
        return updated_chunks
        
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        if not embedding1 or not embedding2:
            return 0.0
            
        if len(embedding1) != len(embedding2):
            logger.error("Embedding dimensions don't match")
            return 0.0
            
        try:
            # Calculate dot product
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            
            # Calculate magnitudes
            magnitude1 = sum(a * a for a in embedding1) ** 0.5
            magnitude2 = sum(b * b for b in embedding2) ** 0.5
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
                
            # Calculate cosine similarity
            similarity = dot_product / (magnitude1 * magnitude2)
            
            # Ensure result is between 0 and 1
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
            
    def get_embedding_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding service configuration.
        
        Returns:
            Dictionary with service information
        """
        model_info = self.model_specs.get(self.model, {})
        
        return {
            "model": self.model,
            "max_tokens": model_info.get("max_tokens", "unknown"),
            "dimensions": model_info.get("dimensions", "unknown"),
            "cost_per_1k_tokens": model_info.get("cost_per_1k_tokens", "unknown"),
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay
        }
        
    def estimate_cost(self, text_count: int, avg_tokens_per_text: int = 100) -> Dict[str, Any]:
        """
        Estimate the cost of embedding generation.
        
        Args:
            text_count: Number of texts to embed
            avg_tokens_per_text: Average tokens per text
            
        Returns:
            Cost estimation information
        """
        model_info = self.model_specs.get(self.model, {})
        cost_per_1k = model_info.get("cost_per_1k_tokens", 0.0001)
        
        total_tokens = text_count * avg_tokens_per_text
        estimated_cost = (total_tokens / 1000) * cost_per_1k
        
        return {
            "text_count": text_count,
            "estimated_total_tokens": total_tokens,
            "cost_per_1k_tokens": cost_per_1k,
            "estimated_cost_usd": round(estimated_cost, 6),
            "model": self.model
        }