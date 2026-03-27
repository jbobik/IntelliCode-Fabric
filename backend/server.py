"""
IntelliCode Fabric — FastAPI Backend v3.0

Improvements:
- Custom models properly added to list and status shown
- Separate /retrieve endpoint (not through /chat)
- Fine-tune with extended params (learning_rate, batch_size, lora_r, etc.)
- Fine-tune timeout fix (background task + proper status polling)
- Streaming via WebSocket with thinking blocks
- All fine-tuned adapter versions shown (not just last)
"""

import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

embedding_engine = None
llm_engine = None
rag_engine = None
orchestrator = None

# Download progress tracker
_download_progress: dict[str, dict] = {}

# Runtime custom models (persist across sessions via list)
_custom_models: list[dict] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_engine, llm_engine, rag_engine, orchestrator

    logger.info("Starting IntelliCode Fabric backend v3...")

    from embeddings import EmbeddingEngine
    from llm_inference import LLMInference
    from rag_engine import RAGEngine
    from agents.orchestrator import AgentOrchestrator

    embedding_engine = EmbeddingEngine(CONFIG["models"]["embeddings"]["model"])
    await embedding_engine.initialize()

    rag_engine = RAGEngine(embedding_engine, CONFIG["rag"])
    llm_engine = LLMInference(CONFIG)
    orchestrator = AgentOrchestrator(llm_engine, rag_engine, CONFIG)

    # Load saved custom models list
    _load_custom_models_list()

    logger.info("Backend initialized.")
    yield

    if llm_engine:
        llm_engine.unload()
    logger.info("Backend shut down.")


app = FastAPI(title="IntelliCode Fabric", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# ═══════════════════════════════════════════════
#  Pydantic Models
# ═══════════════════════════════════════════════

class IndexRequest(BaseModel):
    project_path: str
    force_reindex: bool = False

class ChatRequest(BaseModel):
    message: str
    context_file: Optional[str] = None
    selected_code: Optional[str] = None
    workspace_path: Optional[str] = None  # Full path to workspace root
    conversation_history: list = []
    platform: Optional[str] = None  # 'win32', 'linux', 'darwin'

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
    adapter_id: Optional[str] = None

class ModelDownloadRequest(BaseModel):
    model_id: str

class FineTuneRequest(BaseModel):
    project_path: str
    model_id: Optional[str] = None
    epochs: int = 3
    strategies: Optional[list[str]] = None
    # Extended params
    learning_rate: Optional[float] = None
    batch_size: Optional[int] = None
    gradient_accumulation_steps: Optional[int] = None
    lora_r: Optional[int] = None
    lora_alpha: Optional[int] = None
    lora_dropout: Optional[float] = None
    max_seq_length: Optional[int] = None
    warmup_ratio: Optional[float] = None

class LoadAdapterRequest(BaseModel):
    adapter_id: str

class CustomModelLoadRequest(BaseModel):
    repo: str
    name: str
    quantization: str = "4bit"

class CustomModelDownloadRequest(BaseModel):
    repo: str
    name: str
    quantization: str = "4bit"

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5


def find_model_info(model_id: str) -> Optional[dict]:
    for m in CONFIG["models"]["available"]:
        if m["id"] == model_id:
            return m
    # Also check custom models
    for m in _custom_models:
        if m["id"] == model_id:
            return m
    return None


def _load_custom_models_list():
    """Load list of previously added custom models"""
    global _custom_models
    custom_path = Path(__file__).parent.parent / "data" / "custom_models.json"
    if custom_path.exists():
        try:
            _custom_models = json.loads(custom_path.read_text())
            logger.info(f"Loaded {len(_custom_models)} custom models from disk")
        except Exception as e:
            logger.warning(f"Failed to load custom models: {e}")
            _custom_models = []


def _save_custom_models_list():
    """Save custom models list to disk"""
    custom_path = Path(__file__).parent.parent / "data" / "custom_models.json"
    custom_path.parent.mkdir(parents=True, exist_ok=True)
    custom_path.write_text(json.dumps(_custom_models, indent=2))


# ═══════════════════════════════════════════════
#  Health & Status
# ═══════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": llm_engine.is_loaded() if llm_engine else False,
        "current_model": llm_engine.current_model_id if llm_engine else None,
        "active_adapter": llm_engine.active_adapter if llm_engine else None,
    }


# ═══════════════════════════════════════════════
#  Models
# ═══════════════════════════════════════════════

@app.get("/models")
async def list_models():
    models_dir = Path(__file__).parent.parent / "models"
    result = []

    # Built-in models
    all_models = CONFIG["models"]["available"] + _custom_models

    # Deduplicate by id
    seen_ids = set()
    for m in all_models:
        if m["id"] in seen_ids:
            continue
        seen_ids.add(m["id"])

        model_path = models_dir / m["id"]
        downloaded = False
        if model_path.exists():
            try:
                downloaded = any(model_path.iterdir())
            except Exception as e:
                logger.debug(f"Could not check model directory {model_path}: {e}")
                downloaded = False

        # For custom models loaded from HF directly, check if engine has it
        if not downloaded and llm_engine and llm_engine.current_model_id == m["id"]:
            downloaded = True

        in_progress = _download_progress.get(m["id"], {})
        result.append({
            **m,
            "downloaded": downloaded,
            "active": (llm_engine.current_model_id == m["id"]) if llm_engine else False,
            "download_progress": in_progress.get("progress", 0) if in_progress.get("running") else None,
        })

    return {"models": result, "default": CONFIG["models"]["default"]}


@app.post("/models/select")
async def select_model(req: ModelSelectRequest):
    global orchestrator
    model_info = find_model_info(req.model_id)
    if not model_info:
        raise HTTPException(404, f"Model '{req.model_id}' not found")

    try:
        logger.info(f"Loading model: {req.model_id}" + (f" + adapter: {req.adapter_id}" if req.adapter_id else ""))
        await llm_engine.load_model(model_info, adapter_id=req.adapter_id)
        from agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_engine, rag_engine, CONFIG)
        return {"status": "ok", "model": req.model_id, "adapter": req.adapter_id}
    except Exception as e:
        logger.error(f"Failed to load model: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


@app.post("/models/download")
async def download_model(req: ModelDownloadRequest):
    model_info = find_model_info(req.model_id)
    if not model_info:
        raise HTTPException(404, f"Model '{req.model_id}' not found")

    _download_progress[req.model_id] = {"running": True, "progress": 0, "message": "Starting..."}

    try:
        result = await llm_engine.download_model(model_info,
                                                   progress_callback=_make_download_callback(req.model_id))
        _download_progress[req.model_id] = {"running": False, "progress": 100, "message": "Done"}
        return {"status": "ok", "path": result}
    except Exception as e:
        _download_progress[req.model_id] = {"running": False, "progress": 0, "message": f"Error: {e}"}
        logger.error(f"Download failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


@app.get("/models/download-progress/{model_id}")
async def download_progress(model_id: str):
    return _download_progress.get(model_id, {"running": False, "progress": 0})


@app.post("/models/unload")
async def unload_model():
    if llm_engine:
        llm_engine.unload()
    return {"status": "ok"}


def _make_download_callback(model_id: str):
    def cb(downloaded: int, total: int):
        if total > 0:
            pct = int(100 * downloaded / total)
            _download_progress[model_id] = {
                "running": True,
                "progress": pct,
                "message": f"{downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB",
            }
    return cb


@app.post("/models/load-custom")
async def load_custom_model(req: CustomModelLoadRequest):
    """Load any model from HuggingFace repo or local path"""
    global orchestrator
    try:
        logger.info(f"Loading custom model: {req.repo} (name={req.name}, quant={req.quantization})")

        model_id = req.name.lower().replace(" ", "-").replace("/", "-")

        model_info = {
            "id": model_id,
            "name": req.name,
            "repo": req.repo,
            "type": "causal",
            "quantization": req.quantization if req.quantization != "none" else "",
        }

        await llm_engine.load_model(model_info)

        from agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_engine, rag_engine, CONFIG)

        # Add to custom models list (persistent)
        _add_custom_model(model_info, req.repo)

        return {"status": "ok", "model_id": model_id, "name": req.name}
    except Exception as e:
        logger.error(f"Custom model load failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


@app.post("/models/download-custom")
async def download_custom_model(req: CustomModelDownloadRequest):
    """Download any HuggingFace model and load it"""
    global orchestrator
    try:
        model_id = req.name.lower().replace(" ", "-").replace("/", "-")
        save_path = str(Path(__file__).parent.parent / "models" / model_id)

        logger.info(f"Downloading custom model: {req.repo} → {save_path}")

        from huggingface_hub import snapshot_download
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: snapshot_download(
            repo_id=req.repo,
            local_dir=save_path,
            local_dir_use_symlinks=False,
        ))

        logger.info(f"Downloaded to {save_path}, now loading...")

        model_info = {
            "id": model_id,
            "name": req.name,
            "repo": save_path,
            "type": "causal",
            "quantization": req.quantization if req.quantization != "none" else "",
        }

        await llm_engine.load_model(model_info)

        from agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(llm_engine, rag_engine, CONFIG)

        # Add to custom models list (persistent)
        _add_custom_model(model_info, req.repo)

        return {"status": "ok", "model_id": model_id, "path": save_path}
    except Exception as e:
        logger.error(f"Custom download failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


def _add_custom_model(model_info: dict, original_repo: str):
    """Add custom model to persistent list"""
    # Check if already exists
    for m in _custom_models:
        if m["id"] == model_info["id"]:
            return

    _custom_models.append({
        "id": model_info["id"],
        "name": model_info["name"],
        "repo": original_repo,
        "type": "causal",
        "quantization": model_info.get("quantization", "4bit"),
        "ram_required": "?",
        "description": f"Custom: {original_repo}",
        "tier": "balanced",
        "tags": ["custom"],
    })
    _save_custom_models_list()


# ═══════════════════════════════════════════════
#  Adapters (Fine-tuned) — ALL versions shown
# ═══════════════════════════════════════════════

@app.get("/adapters")
async def list_adapters():
    from fine_tuning import FineTuner
    return {"adapters": FineTuner.list_adapters()}


@app.delete("/adapters/{adapter_id}")
async def delete_adapter(adapter_id: str):
    import shutil
    from fine_tuning import FineTuner
    adapters = FineTuner.list_adapters()
    adapter = next((a for a in adapters if a["id"] == adapter_id), None)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
    shutil.rmtree(adapter["path"], ignore_errors=True)
    return {"status": "ok"}


# ═══════════════════════════════════════════════
#  Index / RAG
# ═══════════════════════════════════════════════

@app.post("/index")
async def index_project(req: IndexRequest):
    try:
        stats = await rag_engine.index_project(req.project_path, req.force_reindex)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Indexing failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════
#  Retrieve — dedicated RAG endpoint
# ═══════════════════════════════════════════════

@app.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    """
    Dedicated retrieval endpoint — separate from /chat.
    Returns relevant code chunks without LLM processing.
    """
    try:
        chunks = await rag_engine.retrieve(req.query, top_k=req.top_k)
        return {
            "status": "ok",
            "chunks": chunks,
            "count": len(chunks),
        }
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════
#  Chat / Generate / Refactor / Inline
# ═══════════════════════════════════════════════

@app.post("/chat")
async def chat(req: ChatRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(400, "No model loaded. Please select a model first.")
    try:
        response = await orchestrator.process_request(
            message=req.message,
            context_file=req.context_file,
            selected_code=req.selected_code,
            conversation_history=req.conversation_history,
            platform=req.platform,
            workspace_path=req.workspace_path,
        )
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    SSE (Server-Sent Events) endpoint для real-time streaming.
    Каждый event — JSON строка с type и data.
    """
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(400, "No model loaded. Please select a model first.")

    event_queue: asyncio.Queue = asyncio.Queue()

    async def stream_callback(event_type: str, data: any = None):
        await event_queue.put({"type": event_type, "data": data})

    async def run_orchestrator():
        try:
            result = await orchestrator.process_request(
                message=req.message,
                context_file=req.context_file,
                selected_code=req.selected_code,
                conversation_history=req.conversation_history,
                stream_callback=stream_callback,
                platform=req.platform,
                workspace_path=req.workspace_path,
            )
            await event_queue.put({"type": "final_result", "data": result})
        except Exception as e:
            logger.error(f"Stream chat error: {e}\n{traceback.format_exc()}")
            await event_queue.put({"type": "error", "data": str(e)})
        finally:
            await event_queue.put(None)  # sentinel

    async def event_generator():
        task = asyncio.create_task(run_orchestrator())
        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            task.cancel()
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/generate")
async def generate_code(req: GenerateRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(400, "No model loaded.")
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
        raise HTTPException(500, str(e))


@app.post("/refactor")
async def refactor_code(req: RefactorRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(400, "No model loaded.")
    try:
        result = await orchestrator.refactor(
            code=req.code, file_path=req.file_path,
            instruction=req.instruction, pattern=req.pattern,
        )
        return result
    except Exception as e:
        logger.error(f"Refactor error: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


@app.post("/inline-edit")
async def inline_edit(req: InlineEditRequest):
    if not llm_engine or not llm_engine.is_loaded():
        raise HTTPException(400, "No model loaded.")
    try:
        context_chunks = await rag_engine.retrieve(req.instruction, top_k=3)
        context_text = "\n\n".join([c["content"] for c in context_chunks])
        result = await orchestrator.inline_edit(
            file_path=req.file_path, code=req.code, instruction=req.instruction,
            line_start=req.line_start, line_end=req.line_end, context=context_text,
        )
        return result
    except Exception as e:
        logger.error(f"Inline edit error: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════
#  Fine-tuning — runs as background task to avoid timeout
# ═══════════════════════════════════════════════

@app.post("/fine-tune")
async def fine_tune(req: FineTuneRequest, background_tasks: BackgroundTasks):
    """
    Starts fine-tuning as a BACKGROUND TASK.
    This fixes the "fetch failed" error — the HTTP response returns immediately,
    and fine-tuning runs in the background. Poll /fine-tune/status for progress.
    """
    try:
        from fine_tuning import FineTuner
        tuner = FineTuner(CONFIG)

        # Build override params
        override_params = {}
        if req.learning_rate is not None:
            override_params["learning_rate"] = req.learning_rate
        if req.batch_size is not None:
            override_params["batch_size"] = req.batch_size
        if req.gradient_accumulation_steps is not None:
            override_params["gradient_accumulation_steps"] = req.gradient_accumulation_steps
        if req.lora_r is not None:
            override_params["lora_r"] = req.lora_r
        if req.lora_alpha is not None:
            override_params["lora_alpha"] = req.lora_alpha
        if req.lora_dropout is not None:
            override_params["lora_dropout"] = req.lora_dropout
        if req.max_seq_length is not None:
            override_params["max_seq_length"] = req.max_seq_length
        if req.warmup_ratio is not None:
            override_params["warmup_ratio"] = req.warmup_ratio

        # Start in background — this is the key fix for "fetch failed"
        background_tasks.add_task(
            _run_fine_tune,
            tuner=tuner,
            project_path=req.project_path,
            model_id=req.model_id or CONFIG["models"]["default"],
            epochs=req.epochs,
            strategies=req.strategies,
            override_params=override_params,
        )

        return {"status": "ok", "message": "Fine-tuning started in background. Poll /fine-tune/status for progress."}
    except Exception as e:
        logger.error(f"Fine-tuning error: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, str(e))


async def _run_fine_tune(tuner, project_path, model_id, epochs, strategies, override_params):
    """Background task for fine-tuning"""
    try:
        await tuner.fine_tune(
            project_path=project_path,
            model_id=model_id,
            epochs=epochs,
            strategies=strategies,
            override_params=override_params,
        )
    except Exception as e:
        logger.error(f"Background fine-tuning failed: {e}", exc_info=True)


@app.get("/fine-tune/status")
async def fine_tune_status():
    from fine_tuning import FineTuner
    return FineTuner.get_status()


# ═══════════════════════════════════════════════
#  WebSocket streaming with thinking blocks
# ═══════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket connected")
    try:
        while True:
            data = await ws.receive_text()
            message = json.loads(data)

            if message["type"] == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            if message["type"] == "chat_stream":
                if not llm_engine or not llm_engine.is_loaded():
                    await ws.send_text(json.dumps({"type": "error", "content": "No model loaded"}))
                    continue

                try:
                    context_chunks = await rag_engine.retrieve(message["content"], top_k=5)
                    context_text = "\n\n".join([
                        f"// {c['metadata']['file_path']}\n{c['content']}"
                        for c in context_chunks
                    ])
                    prompt = _build_generation_prompt(
                        message["content"],
                        message.get("selected_code"),
                        context_text,
                        "chat"
                    )

                    in_think = False
                    think_buffer = ""

                    async for token in llm_engine.generate_stream(prompt):
                        # Detect thinking blocks and send them separately
                        if "<think>" in token:
                            in_think = True
                            think_buffer = ""
                            await ws.send_text(json.dumps({"type": "thinking_start"}))
                            continue
                        if "</think>" in token:
                            in_think = False
                            await ws.send_text(json.dumps({
                                "type": "thinking_end",
                                "content": think_buffer,
                            }))
                            continue
                        if in_think:
                            think_buffer += token
                            await ws.send_text(json.dumps({
                                "type": "thinking_token",
                                "content": token,
                            }))
                        else:
                            await ws.send_text(json.dumps({"type": "token", "content": token}))

                    await ws.send_text(json.dumps({
                        "type": "stream_end",
                        "context_files": [c["metadata"]["file_path"] for c in context_chunks],
                    }))
                except Exception as e:
                    await ws.send_text(json.dumps({"type": "error", "content": str(e)}))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# ═══════════════════════════════════════════════
#  Prompt builders
# ═══════════════════════════════════════════════

def _build_generation_prompt(prompt, selected_code, context, instruction):
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


if __name__ == "__main__":
    uvicorn.run("server:app", host=CONFIG["server"]["host"],
                port=CONFIG["server"]["port"], reload=False, log_level="info")