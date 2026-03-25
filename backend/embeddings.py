"""
Embedding engine using sentence-transformers for RAG
"""

import asyncio
import logging
from typing import Optional

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.dimension: int = 384
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Load the embedding model"""
        logger.info(f"Loading embedding model: {self.model_name}")

        loop = asyncio.get_event_loop()
        self.model = await loop.run_in_executor(None, self._load_model)

        # Get actual dimension
        test_emb = self.model.encode(["test"])
        self.dimension = test_emb.shape[1]
        logger.info(f"Embedding model loaded. Dimension: {self.dimension}")

    def _load_model(self) -> SentenceTransformer:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer(self.model_name, device=device)
        return model

    async def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts"""
        async with self._lock:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, lambda: self.model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
            )
            return embeddings

    async def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text"""
        result = await self.embed([text])
        return result[0]