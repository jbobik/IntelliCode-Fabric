"""
AI Code Partner — FastAPI Backend Server
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Load Config ───
CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# ─── Global instances (set during lifespan) ───
embedding_engine = None
llm_engine = None
rag_engine = None
orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_engine, llm_engine, rag_engine, orchestrator

    logger.info("Starting AI Code Partner backend...")

    from embeddings import EmbeddingEngine
    from llm_inference import LLMInference
    from rag_engine import RAGEngine
    from agents.orchestrator import AgentOrchestrator

    # 1) Embeddings
    embedding_engine = EmbeddingEngine(CONFIG["models"]["embeddings"]["model"])
    await embedding_engine.initialize()

    # 2) RAG
    rag_engine = RAGEngine(embedding_engine, CONFIG["rag"])

    # 3) LLM (starts unloaded)
    llm_engine = LLMInference(CONFIG)

    # 4) Orchestrator
    orchestrator = AgentOrchestrator(llm_engine, rag_engine, CONFIG)

    logger.info("Backend initialized. Waiting for model selection...")
    yield

    # Cleanup
    if llm_engine:
        llm_engine.unload()
    logger.info("Backend shut down.")


app = FastAPI(title="AI Code Partner", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════
#  Request / Response Models
# ═══════════════════════════════════════════════

class IndexRequest(BaseModel):
    project_path: str
    force_reindex: bool = False


class ChatRequest(BaseModel):
    message: str
    context_file: Optional[str] = None
    selected_code: Optional[str] = None
    conversation_history: list = []


class GenerateRequest(BaseModel):
    prompt: str
    file_path: Optional[str] = None
    selected_code: Optional[str] = None
    instruction: str = "generate"


class RefactorRequest(BaseModel):
    code: str
    file_path: str
    instruction: str
    pattern: Optional[str] = None


class InlineEditRequest(BaseModel):
    file_path: str
    code: str
    instruction: str
    line_start: int
    line_end: int


class ModelSelectRequest(BaseModel):
    model_id: str


class ModelDownloadRequest(BaseModel):
    model_id: str


class FineTuneRequest(BaseModel):
    project_path: str
    model_id: Optional[str] = None
    epochs: int = 3


# ═══════════════════════════════════════════════
#  Helper: find model info by id
# ═══════════════════════════════════════════════

def find_model_info(model_id: str) -> Optional[dict]:
    for m in CONFIG["models"]["available"]:
        if m["id"] == model_id:
            return m
    return None


# ═══════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": llm_engine.is_loaded() if llm_engine else False,
        "current_model": llm_engine.current_model_id if llm_engine else None,
    }


# ─── Models ───

@app.get("/models")
async def list_models():
    models_dir = Path(__file__).parent.parent / "models"
    result = []
    for m in CONFIG["models"]["available"]:
        model_path = models_dir / m["id"]
        downloaded = False
        if model_path.exists():
            try:
                downloaded = any(model_path.iterdir())
            except Exception:
                downloaded = False
        result.append({
            **m,
            "downloaded": downloaded,
            "active": (llm_engine.current_model_id == m["id"]) if llm_engine else False,
        })
    return {"models": result, "default": CONFIG["models"]["default"]}


@app.post("/models/select")
async def select_model(req: ModelSelectRequest):
    """Load a model for inference"""
    global orchestrator

    model_info = find_model_info(req.model_id)
    if not model_info:
        raise HTTPException(status_code=404, detail=f"Model '{req.model_id}' not found in config")

    try:
        logger.info(f"=== Loading model: {req.model_id} ===")
        await llm_engine.load_model(model_info)

        # Re-create orchestrator with loaded model
        from agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_engine, rag_engine, CONFIG)

        logger.info(f"=== Model {req.model_id} ready ===")
        return {"status": "ok", "model": req.model_id}
    except Exception as e:
        logger.error(f"Failed to load model: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/models/download")
async def download_model(req: ModelDownloadRequest):
    """Download a model from HuggingFace"""
    model_info = find_model_info(req.model_id)
    if not model_info:
        raise HTTPException(status_code=404, detail=f"Model '{req.model_id}' not found")

    try:
        result = await llm_engine.download_model(model_info)
        return {"status": "ok", "path": result}
    except Exception as e:
        logger.error(f"Download failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/models/unload")
async def unload_model():
    """Unload current model"""
    if llm_engine:
        llm_engine.unload()
    return {"status": "ok"}


# ─── Index ───

@app.post("/index")
async def index_project(req: IndexRequest):
    try:
        stats = await rag_engine.index_project(req.project_path, req.force_reindex)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Indexing failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Chat ───

@app.post("/chat")
async def chat(req: ChatRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(status_code=400, detail="No model loaded. Please select a model first.")

    try:
        response = await orchestrator.process_request(
            message=req.message,
            context_file=req.context_file,
            selected_code=req.selected_code,
            conversation_history=req.conversation_history,
        )
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Generate ───

@app.post("/generate")
async def generate_code(req: GenerateRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(status_code=400, detail="No model loaded.")

    try:
        context_chunks = await rag_engine.retrieve(req.prompt, top_k=5)
        context_text = "\n\n".join([c["content"] for c in context_chunks])

        prompt = _build_generation_prompt(req.prompt, req.selected_code, context_text, req.instruction)
        result = await llm_engine.generate(prompt)
        return {
            "generated_code": result,
            "context_files": [c["metadata"]["file_path"] for c in context_chunks],
        }
    except Exception as e:
        logger.error(f"Generation error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Refactor ───

@app.post("/refactor")
async def refactor_code(req: RefactorRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(status_code=400, detail="No model loaded.")

    try:
        result = await orchestrator.refactor(
            code=req.code,
            file_path=req.file_path,
            instruction=req.instruction,
            pattern=req.pattern,
        )
        return result
    except Exception as e:
        logger.error(f"Refactor error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Inline Edit ───

@app.post("/inline-edit")
async def inline_edit(req: InlineEditRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(status_code=400, detail="No model loaded.")

    try:
        context_chunks = await rag_engine.retrieve(req.instruction, top_k=3)
        context_text = "\n\n".join([c["content"] for c in context_chunks])

        result = await orchestrator.inline_edit(
            file_path=req.file_path,
            code=req.code,
            instruction=req.instruction,
            line_start=req.line_start,
            line_end=req.line_end,
            context=context_text,
        )
        return result
    except Exception as e:
        logger.error(f"Inline edit error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Fine-tune ───

@app.post("/fine-tune")
async def fine_tune(req: FineTuneRequest):
    try:
        from fine_tuning import FineTuner
        tuner = FineTuner(CONFIG)
        result = await tuner.fine_tune(
            project_path=req.project_path,
            model_id=req.model_id or CONFIG["models"]["default"],
            epochs=req.epochs,
        )
        return result
    except Exception as e:
        logger.error(f"Fine-tuning error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fine-tune/status")
async def fine_tune_status():
    from fine_tuning import FineTuner
    return FineTuner.get_status()


# ═══════════════════════════════════════════════
#  Prompt builders
# ═══════════════════════════════════════════════

def _build_generation_prompt(
    prompt: str,
    selected_code: Optional[str],
    context: str,
    instruction: str,
) -> str:
    system = (
        "You are an expert code generator. Generate clean, well-documented, production-ready code. "
        "Follow existing project conventions visible in the context. Output ONLY the code, no explanations unless asked."
    )
    user_msg = ""
    if context:
        user_msg += f"## Project Context:\n```\n{context}\n```\n\n"
    if selected_code:
        user_msg += f"## Existing Code:\n```\n{selected_code}\n```\n\n"
    user_msg += f"## Instruction: {instruction}\n## Request: {prompt}"

    return f"<|system|>\n{system}\n<|end|>\n<|user|>\n{user_msg}\n<|end|>\n<|assistant|>"


# ═══════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=CONFIG["server"]["host"],
        port=CONFIG["server"]["port"],
        reload=False,
        log_level="info",
    )