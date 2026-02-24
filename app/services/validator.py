# app/validator.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import re
import yaml


SUPPORTED_ENGINES = {"ollama", "vllm", "openai"}
SUPPORTED_MODEL_TYPES = {"llm", "vlm", "embedding", "reranker"}


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]
    warnings: List[str]
    normalized_config: Dict[str, Any]


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config YAML must be a mapping (top-level dict).")
    return data


def _is_http_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s.strip()))


def normalize_params(params: Any) -> Dict[str, Any]:
    """
    Normalize YAML params to a dict.

    Supports:
      params:
        - temperature: 0.7
        - max-tokens: 1024
        - stream: false

    Also supports:
      params: { temperature: 0.7, ... }
      params: null
    """
    if params is None:
        return {}

    if isinstance(params, dict):
        return dict(params)

    if isinstance(params, list):
        out: Dict[str, Any] = {}
        for item in params:
            if isinstance(item, dict) and len(item) == 1:
                k, v = next(iter(item.items()))
                out[str(k)] = v
            elif isinstance(item, str):
                if ":" in item:
                    k, v = item.split(":", 1)
                    out[k.strip()] = v.strip()
                elif "=" in item:
                    k, v = item.split("=", 1)
                    out[k.strip()] = v.strip()
        return out

    return {}


def _normalize_model_type(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().lower()
    aliases = {
        "text": "llm",
        "chat": "llm",
        "llm": "llm",
        "vision": "vlm",
        "multimodal": "vlm",
        "vlm": "vlm",
        "embed": "embedding",
        "embedding": "embedding",
        "rerank": "reranker",
        "reranker": "reranker",
    }
    return aliases.get(raw, raw)


def _normalize_aliases(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            continue
        alias = item.strip()
        if not alias or alias in seen:
            continue
        seen.add(alias)
        out.append(alias)
    return out


def validate_config_dict(cfg: Dict[str, Any]) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    normalized = dict(cfg)

    serving = normalized.get("serving")
    if not isinstance(serving, dict):
        errors.append("Missing or invalid 'serving' section (must be a mapping).")
        return ValidationResult(False, errors, warnings, normalized)

    engine = serving.get("engine")
    if not isinstance(engine, str) or not engine.strip():
        errors.append("serving.engine is required and must be a non-empty string.")
    else:
        engine = engine.strip()
        serving["engine"] = engine
        if engine not in SUPPORTED_ENGINES:
            warnings.append(
                f"serving.engine='{engine}' is not in supported list {sorted(SUPPORTED_ENGINES)}. "
                "Validation will continue, but runtime may fail."
            )

    def _validate_url_field(field_name: str) -> None:
        value = serving.get(field_name)
        if value is None:
            return
        if not isinstance(value, str) or not value.strip():
            errors.append(f"serving.{field_name} must be a non-empty string when provided.")
            return

        value = value.strip()
        serving[field_name] = value
        if not _is_http_url(value):
            errors.append(f"serving.{field_name} must start with http:// or https:// (got: {value})")
        if "{0}" in value:
            warnings.append(
                f"serving.{field_name} contains '{{0}}' placeholder. "
                "If you are using a single backend container, prefer a fixed OpenAI-compatible endpoint URL."
            )

    _validate_url_field("base-url")
    _validate_url_field("ollama-base-url")
    _validate_url_field("vllm-base-url")

    base_url = serving.get("base-url")
    ollama_base_url = serving.get("ollama-base-url")
    vllm_base_url = serving.get("vllm-base-url")
    if not any(isinstance(v, str) and v.strip() for v in (base_url, ollama_base_url, vllm_base_url)):
        errors.append(
            "At least one backend URL is required: serving.base-url or serving.ollama-base-url or serving.vllm-base-url."
        )

    models = serving.get("models")
    if models is None:
        errors.append("serving.models is required (must be a list).")
        models = []
        serving["models"] = models

    if not isinstance(models, list):
        errors.append("serving.models must be a list.")
        models = []
        serving["models"] = models

    if isinstance(models, list) and len(models) == 0:
        warnings.append("serving.models is empty. Gateway will have nothing to route.")

    normalized_models: List[Dict[str, Any]] = []
    for i, m in enumerate(models if isinstance(models, list) else []):
        if not isinstance(m, dict):
            errors.append(f"serving.models[{i}] must be a mapping (dict).")
            continue

        name = m.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"serving.models[{i}].name is required and must be a non-empty string.")
            continue

        m2 = dict(m)
        m2["name"] = name.strip()
        m2["params"] = normalize_params(m.get("params"))
        m2["aliases"] = _normalize_aliases(m.get("aliases"))

        model_type = _normalize_model_type(m.get("type"))
        if model_type is not None:
            m2["type"] = model_type
            if model_type not in SUPPORTED_MODEL_TYPES:
                warnings.append(
                    f"serving.models[{i}].type='{model_type}' is not in supported list "
                    f"{sorted(SUPPORTED_MODEL_TYPES)}. Runtime may ignore special routing."
                )

        model_engine = m.get("engine", m.get("backend"))
        if model_engine is not None:
            if not isinstance(model_engine, str) or not model_engine.strip():
                errors.append(f"serving.models[{i}].engine must be a non-empty string when provided.")
            else:
                engine_norm = model_engine.strip().lower()
                m2["engine"] = engine_norm
                if engine_norm not in SUPPORTED_ENGINES:
                    warnings.append(
                        f"serving.models[{i}].engine='{engine_norm}' is not in supported list "
                        f"{sorted(SUPPORTED_ENGINES)}. Runtime may fail to route."
                    )

        path = m2.get("path")
        if isinstance(path, str) and path.strip():
            if "models/" in path and not path.startswith(("models/", "./models/")):
                warnings.append(
                    f"serving.models[{i}].path='{path}' looks non-standard. This is only a warning."
                )

        normalized_models.append(m2)

    serving["models"] = normalized_models
    normalized["serving"] = serving

    ok = len(errors) == 0
    return ValidationResult(ok=ok, errors=errors, warnings=warnings, normalized_config=normalized)


def validate_config_file(path: str | Path) -> ValidationResult:
    p = Path(path)
    cfg = _load_yaml(p)
    return validate_config_dict(cfg)


def print_result(res: ValidationResult) -> None:
    if res.ok:
        print("Config validation PASSED")
    else:
        print("Config validation FAILED")

    if res.warnings:
        print("")
        print("Warnings:")
        for w in res.warnings:
            print(f"  - {w}")

    if res.errors:
        print("")
        print("Errors:")
        for e in res.errors:
            print(f"  - {e}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate ViLMS gateway config.yaml")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "configs" / "config.yaml"),
        help="Path to config.yaml (default: ./app/configs/config.yaml)",
    )
    args = parser.parse_args()

    res = validate_config_file(args.config)
    print_result(res)
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
