"""
RAG Engine — project indexing, chunking, retrieval
"""

import asyncio
import hashlib
import logging
import os
import re
import fnmatch
from pathlib import Path
from typing import Optional

import chromadb

from embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)


class CodeChunker:
    """Intelligent code chunking that respects code structure"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_file(self, content: str, file_path: str) -> list[dict]:
        """Split file into semantic chunks"""
        ext = Path(file_path).suffix.lower()
        chunks = self._structural_chunk(content, file_path, ext)
        if not chunks:
            chunks = self._line_based_chunk(content, file_path)
        return chunks

    def _structural_chunk(self, content: str, file_path: str, ext: str) -> list[dict]:
        """Chunk by code structures (functions, classes)"""
        chunks = []

        patterns = {
            ".py": [
                r'^(class\s+\w+.*?(?=\nclass\s|\Z))',
                r'^(def\s+\w+.*?(?=\ndef\s|\nclass\s|\Z))',
                r'^(async\s+def\s+\w+.*?(?=\ndef\s|\nasync\s+def\s|\nclass\s|\Z))',
            ],
            ".js": [
                r'((?:export\s+)?(?:async\s+)?function\s+\w+.*?(?=\nfunction\s|\nexport\s|\Z))',
                r'((?:export\s+)?class\s+\w+.*?(?=\nclass\s|\nexport\s|\Z))',
            ],
            ".ts": [
                r'((?:export\s+)?(?:async\s+)?function\s+\w+.*?(?=\nfunction\s|\nexport\s|\Z))',
                r'((?:export\s+)?class\s+\w+.*?(?=\nclass\s|\nexport\s|\Z))',
                r'((?:export\s+)?interface\s+\w+.*?(?=\ninterface\s|\nexport\s|\Z))',
            ],
            ".java": [
                r'((?:public|private|protected)\s+class\s+\w+.*?(?=\npublic\s+class|\Z))',
            ],
        }

        ext_map = {".tsx": ".ts", ".jsx": ".js", ".mjs": ".js", ".cjs": ".js"}
        lookup_ext = ext_map.get(ext, ext)

        if lookup_ext not in patterns:
            return []

        for pattern in patterns[lookup_ext]:
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                chunk_text = match.group(1).strip()
                if len(chunk_text) > 30:
                    if len(chunk_text) > self.chunk_size * 3:
                        sub_chunks = self._line_based_chunk(chunk_text, file_path)
                        chunks.extend(sub_chunks)
                    else:
                        start_line = content[:match.start()].count('\n') + 1
                        end_line = start_line + chunk_text.count('\n')
                        chunks.append({
                            "content": chunk_text,
                            "metadata": {
                                "file_path": file_path,
                                "line_start": start_line,
                                "line_end": end_line,
                                "chunk_type": "structural",
                            }
                        })

        return chunks

    def _line_based_chunk(self, content: str, file_path: str) -> list[dict]:
        """Fallback line-based chunking"""
        lines = content.split('\n')
        chunks = []
        current_chunk_lines = []
        current_length = 0
        chunk_start_line = 1

        for i, line in enumerate(lines):
            line_len = len(line)
            if current_length + line_len > self.chunk_size and current_chunk_lines:
                chunk_text = '\n'.join(current_chunk_lines)
                chunks.append({
                    "content": chunk_text,
                    "metadata": {
                        "file_path": file_path,
                        "line_start": chunk_start_line,
                        "line_end": chunk_start_line + len(current_chunk_lines) - 1,
                        "chunk_type": "line_based",
                    }
                })
                overlap_lines = max(1, self.chunk_overlap // 40)
                current_chunk_lines = current_chunk_lines[-overlap_lines:]
                current_length = sum(len(l) for l in current_chunk_lines)
                chunk_start_line = i + 1 - len(current_chunk_lines) + 1

            current_chunk_lines.append(line)
            current_length += line_len

        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines)
            chunks.append({
                "content": chunk_text,
                "metadata": {
                    "file_path": file_path,
                    "line_start": chunk_start_line,
                    "line_end": chunk_start_line + len(current_chunk_lines) - 1,
                    "chunk_type": "line_based",
                }
            })

        return chunks


class RAGEngine:
    def __init__(self, embedding_engine: EmbeddingEngine, config: dict):
        self.embedding_engine = embedding_engine
        self.config = config
        self.chunker = CodeChunker(
            chunk_size=config.get("chunk_size", 512),
            chunk_overlap=config.get("chunk_overlap", 50),
        )
        self.supported_extensions = set(config.get("supported_extensions", []))
        self.ignore_patterns = config.get("ignore_patterns", [])

        db_path = str(Path(__file__).parent.parent / "data" / "chroma_db")
        os.makedirs(db_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = None
        self._current_project: Optional[str] = None
        self._lock = asyncio.Lock()
        self._global_chunk_counter = 0

    def _should_ignore(self, path: str) -> bool:
        path_parts = Path(path).parts
        for pattern in self.ignore_patterns:
            if any(fnmatch.fnmatch(part, pattern) for part in path_parts):
                return True
            if fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        return False

    def _get_collection_name(self, project_path: str) -> str:
        path_hash = hashlib.md5(project_path.encode()).hexdigest()[:12]
        project_name = Path(project_path).name
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', project_name)[:40]
        name = f"{clean_name}_{path_hash}"
        # ChromaDB requires length 3-63
        if len(name) < 3:
            name = name + "___"
        return name[:63]

    async def index_project(self, project_path: str, force_reindex: bool = False) -> dict:
        async with self._lock:
            logger.info(f"Indexing project: {project_path}")

            collection_name = self._get_collection_name(project_path)

            if force_reindex:
                try:
                    self.chroma_client.delete_collection(collection_name)
                    logger.info(f"Deleted existing collection: {collection_name}")
                except Exception:
                    pass

            self.collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._current_project = project_path
            self._global_chunk_counter = 0

            # Scan files
            files_to_index = []
            project = Path(project_path)
            for ext in self.supported_extensions:
                for f in project.rglob(f"*{ext}"):
                    rel_path = str(f.relative_to(project))
                    if not self._should_ignore(rel_path):
                        files_to_index.append(f)

            logger.info(f"Found {len(files_to_index)} files to index")

            total_chunks = 0
            errors = 0
            batch_size = 50

            for i in range(0, len(files_to_index), batch_size):
                batch = files_to_index[i:i + batch_size]
                batch_chunks = []

                for file_path in batch:
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        if not content.strip():
                            continue

                        rel_path = str(file_path.relative_to(project))
                        chunks = self.chunker.chunk_file(content, rel_path)
                        batch_chunks.extend(chunks)
                    except Exception as e:
                        logger.warning(f"Error processing {file_path}: {e}")
                        errors += 1

                if batch_chunks:
                    await self._store_chunks(batch_chunks)
                    total_chunks += len(batch_chunks)

                logger.info(
                    f"Indexed {min(i + batch_size, len(files_to_index))}/{len(files_to_index)} files"
                )

            stats = {
                "total_files": len(files_to_index),
                "total_chunks": total_chunks,
                "errors": errors,
                "project_path": project_path,
            }
            logger.info(f"Indexing complete: {stats}")
            return stats

    async def _store_chunks(self, chunks: list[dict]):
        """Store chunks in ChromaDB with guaranteed unique IDs"""
        texts = [c["content"] for c in chunks]
        embeddings = await self.embedding_engine.embed(texts)

        ids = []
        documents = []
        metadatas = []
        embedding_list = []

        seen_ids = set()

        for i, chunk in enumerate(chunks):
            self._global_chunk_counter += 1

            # Build unique ID using file + line + counter
            raw_id = (
                f"{chunk['metadata']['file_path']}"
                f":{chunk['metadata']['line_start']}"
                f":{self._global_chunk_counter}"
            )
            chunk_id = hashlib.md5(raw_id.encode()).hexdigest()

            # Extra safety: if still duplicate (shouldn't happen), append counter
            while chunk_id in seen_ids:
                self._global_chunk_counter += 1
                raw_id = f"{raw_id}_{self._global_chunk_counter}"
                chunk_id = hashlib.md5(raw_id.encode()).hexdigest()

            seen_ids.add(chunk_id)
            ids.append(chunk_id)
            documents.append(chunk["content"])
            metadatas.append(chunk["metadata"])
            embedding_list.append(embeddings[i].tolist())

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embedding_list,
        )

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.collection:
            logger.warning("No collection loaded — returning empty context")
            return []

        try:
            count = self.collection.count()
            if count == 0:
                return []

            query_embedding = await self.embedding_engine.embed_single(query)

            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=min(top_k, count),
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    chunks.append({
                        "content": doc,
                        "metadata": meta,
                        "relevance_score": 1 - dist,
                    })

            return chunks

        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []

    async def get_file_context(self, file_path: str) -> list[dict]:
        if not self.collection:
            return []

        try:
            results = self.collection.get(
                where={"file_path": file_path},
                include=["documents", "metadatas"],
            )

            chunks = []
            if results["documents"]:
                for doc, meta in zip(results["documents"], results["metadatas"]):
                    chunks.append({"content": doc, "metadata": meta})

            return chunks
        except Exception as e:
            logger.error(f"File context error: {e}")
            return []