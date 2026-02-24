# ViLMS Finetune / LoRA Status

## 1. Summary

- Current repo scope is `serving gateway` (API + routing + Docker orchestration)
- Finetune / LoRA / QLoRA training pipeline is `not implemented` in this codebase
- Recent work improved config-based model expansion (`type`, `engine`, `aliases`) to make future integration easier

## 2. Scope Clarification

This repository currently focuses on:
- OpenAI-compatible API serving
- Backend routing (`ollama` / `vllm`)
- Config-driven model selection and aliases
- Deployment orchestration via generated `docker-compose.yaml`

Finetune / LoRA work should be implemented as a separate training workflow, then integrated back into serving through model artifacts.

## 3. Current Status (Detailed)

### Done

- Inference gateway for `ollama` / `vllm` with OpenAI-compatible routes
- Model alias mapping and config-driven routing
- Jetson-aware inference routing and payload trimming
- Documentation of current LoRA status and implementation direction

### Not Done

- Training pipeline for finetune / LoRA / QLoRA
- Dataset preparation pipeline / manifests
- Adapter registry / adapter selection at request time
- Adapter merge/export workflow for serving on `ollama` or `vllm`
- Runtime adapter loading support in gateway config/runtime

## 4. Proposed Implementation Phases

### Phase 1: Dataset + Training Skeleton

- Add `train/` folder with:
  - dataset manifest format (JSONL)
  - config templates (`yaml`) for LoRA / QLoRA
  - launch scripts (`bash`) for single-GPU runs
  - optional Jetson-safe experimental configs (small-scale only)
- Define output artifact convention:
  - `artifacts/<run_id>/adapter/`
  - `artifacts/<run_id>/metrics.json`
  - `artifacts/<run_id>/merged/` (optional)

### Phase 2: Adapter Packaging for Serving

- Document two serving paths:
  - `merged model` for `ollama` import / `vllm` direct serving
  - `adapter + base model` for runtimes that support adapter loading
- Add conversion/export scripts:
  - merge LoRA -> HF weights
  - optional quantization/export step (if needed for deployment)

### Phase 3: Serving Integration in ViLMS

- Extend `config.yaml` with optional adapter metadata:
  - alias -> base model + adapter artifact path
- Add validation and alias resolution rules for adapter-backed models
- Add operational docs for rollout / rollback of fine-tuned models
- Add smoke tests for adapter-backed serving entries (if runtime supports it)

## 5. Open Risks / Gaps

- Scope creep risk: mixing training pipeline concerns into gateway runtime too early
- Artifact compatibility risk between training outputs and serving runtimes (`ollama`, `vllm`)
- Hardware limitations for local experiments (especially Jetson and CPU-only environments)
- Evaluation/benchmark criteria are not defined yet (quality regression risk)

## 6. Recommendations (Current)

1. Keep this repo focused on serving until a minimal external LoRA training pipeline is ready.
2. Start domain adaptation with prompt/system-message tuning before moving to LoRA.
3. If LoRA is required, train externally and integrate merged artifacts first (simpler serving path).
4. Define artifact naming/versioning conventions early to avoid deployment confusion later.
