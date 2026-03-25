# AI Code Partner — Analysis & Research

## Competitor Analysis

### GitHub Copilot Chat
- **Strengths**: Massive training corpus, GitHub integration, multi-language
- **Weaknesses**: Cloud-only, no customization, $10-19/mo, code sent to Microsoft
- **Our advantage**: 100% local, fine-tunable, free

### Cursor
- **Strengths**: Excellent UX, full project context, fast
- **Weaknesses**: Separate fork of VS Code, cloud models, $20/mo Pro
- **Our advantage**: VS Code plugin (no app switch), local inference, fine-tuning

### Cody (Sourcegraph)
- **Strengths**: Powerful enterprise RAG
- **Weaknesses**: Sourcegraph dependency, complex enterprise setup
- **Our advantage**: Zero dependencies, self-contained

### Continue.dev
- **Strengths**: Open source, Ollama support
- **Weaknesses**: No multi-agent, less polished UX, no fine-tuning
- **Our advantage**: Multi-agent pipeline, QLoRA fine-tuning, better UI

---

## NDA-Grade / Corporate Model Research

### What are "NDA-grade" models?
Companies like Bloomberg, Google, Morgan Stanley, and others fine-tune open-source
base models on their proprietary codebases. The result is a model that:
- Knows internal APIs and library conventions
- Uses company-specific naming patterns
- Understands internal architecture and module relationships
- Won't leak proprietary patterns to third parties

### How to replicate this approach with AI Code Partner

**Step 1 — Choose the right base model**

| Base Model | Why it's good for fine-tuning |
|---|---|
| `Qwen2.5-Coder-7B` (base) | Best general code understanding, Apache 2.0 |
| `DeepSeek-Coder-6.7B` (base) | Excellent algorithm reasoning, MIT |
| `StarCoder2-7B` (base) | FIM (fill-in-middle) support, BigCode OpenRAIL |

**Step 2 — Extract training data (done automatically by our FineTuner)**

Our system extracts 5 types of training signals:
1. **Docstring → Implementation** — the model learns to implement functions matching your documentation style
2. **Comment → Code** — learns inline comment conventions
3. **File completion** — learns module-level patterns and architecture
4. **Signature → Body** — learns API surface patterns
5. **Test → Implementation** — reverse TDD, understands test-first patterns

**Step 3 — LoRA training**

We use QLoRA (Quantized LoRA) because:
- Only ~0.1% of parameters are trained (attention projections)
- Adapter is only 50-100MB instead of GBs
- Multiple adapters can coexist for different projects
- Training takes 15-60 minutes on a laptop GPU

**Step 4 — Load adapter for inference**

Adapters are per-project. You can have:
- `my-startup__adapter` for your main codebase
- `client-project__adapter` for a specific client's conventions
- `legacy-system__adapter` for maintaining old code

### Why this beats Cursor/Copilot for corporate use

| Feature | Copilot / Cursor | AI Code Partner |
|---|---|---|
| Data stays local | ❌ | ✅ |
| Learns your conventions | ❌ | ✅ Fine-tuning |
| Works offline | ❌ | ✅ |
| Monthly cost | $10-20/dev | $0 |
| Custom model per project | ❌ | ✅ |
| Regulatory compliance (GDPR, HIPAA) | Difficult | ✅ Trivial |

---

## Recommended Models by Use Case

### Absolute minimum (old laptop, CPU only)
→ **Qwen2.5-Coder-0.5B** (2GB RAM)
- Basic completions, simple questions
- ~2-5 tokens/sec on CPU

### Daily driver on modest hardware
→ **Qwen2.5-Coder-1.5B** (3GB RAM)  ⭐ Recommended default
- Excellent quality/speed for 1.5B
- ~5-15 tokens/sec on CPU, ~30-60 on GPU

### Best balance
→ **Qwen2.5-Coder-7B** (8GB RAM / 8GB VRAM)
- Near-GPT-3.5 quality for code tasks
- ~10-20 tokens/sec on GPU

### Best quality locally
→ **Qwen2.5-Coder-14B** (16GB RAM / 16GB VRAM)
- Near-GPT-4 quality on code
- Recommended for teams with a shared inference server

### For fine-tuning (base models, no instruction tuning)
→ **Qwen2.5-Coder-7B-Base** or **DeepSeek-Coder-6.7B-Base**
- No instruction-following bias to override
- Better starting point for domain adaptation

---

## Architecture Overview

```
VS Code Extension (TypeScript)
│
├── SidebarProvider  — webview chat UI with model picker
├── InlineEditProvider — Ctrl+Shift+E inline editing with diff
├── ModelManager — download/select models
└── AgentOrchestrator (TS) — client-side intent routing
    │
    └── HTTP → FastAPI Backend (Python)
        │
        ├── /chat    → AgentOrchestrator (Python)
        │              ├── AnalystAgent   — RAG + code analysis
        │              ├── CoderAgent     — code generation
        │              ├── RefactorAgent  — pattern-based refactor
        │              └── TesterAgent    — test generation
        │
        ├── /fine-tune → FineTuner (QLoRA)
        │                ├── 5 extraction strategies
        │                ├── Dynamic LoRA target detection
        │                └── Per-project adapter storage
        │
        ├── /models   → Model list with tier grouping
        ├── /adapters → List fine-tuned adapters
        │
        └── RAGEngine → ChromaDB
                        ├── Structural chunking (function/class)
                        └── Embedding (all-MiniLM-L6-v2)
```