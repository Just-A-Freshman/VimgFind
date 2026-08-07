from __future__ import annotations
"""Tokenizers for multimodal model text encoding.

Provides three pure-Python tokenizer implementations:
  - BertWordPieceTokenizer (BERT / Chinese-CLIP style)
  - CLIPBpeTokenizer       (CLIP / GPT-2 style)
  - UnigramTokenizer       (SentencePiece style)

Plus a factory function `create_tokenizer()` that auto-detects
the tokenizer type from a model directory.
"""

from .base import BaseTokenizer
from .bert_tokenizer import BertWordPieceTokenizer
from .clip_tokenizer import CLIPBpeTokenizer
from .unigram_tokenizer import UnigramTokenizer

__all__ = [
    "BaseTokenizer",
    "BertWordPieceTokenizer",
    "CLIPBpeTokenizer",
    "UnigramTokenizer",
    "create_tokenizer",
]


def _detect_lower_case(model_dir: str) -> bool:
    """Detect do_lower_case from tokenizer_config.json if present."""
    import json as _json
    from pathlib import Path

    config_path = Path(model_dir) / "tokenizer_config.json"
    if config_path.exists():
        try:
            with open(str(config_path), "r", encoding="utf-8") as f:
                cfg = _json.load(f)
            return bool(cfg.get("do_lower_case", False))
        except Exception:
            pass
    return False


def create_tokenizer(model_dir: str) -> BaseTokenizer | None:
    """Auto-detect tokenizer type from model directory and create it.

    Detection priority:
      1. vocab.txt present             → BertWordPieceTokenizer
      2. merges.txt + vocab.json present → CLIPBpeTokenizer
      3. .model file present           → UnigramTokenizer
      4. tokenizer.json present        → CLIPBpeTokenizer (BPE)
      5. none of the above             → None

    Also reads tokenizer_config.json for do_lower_case setting.
    """
    import os
    from pathlib import Path

    path = Path(model_dir)
    if not path.is_dir():
        path = path.parent

    do_lower = _detect_lower_case(str(path))

    # BERT WordPiece
    vocab_txt = path / "vocab.txt"
    if vocab_txt.exists():
        return BertWordPieceTokenizer(str(vocab_txt), do_lower_case=do_lower)

    # CLIP BPE: merges.txt + vocab.json
    merges_txt = path / "merges.txt"
    vocab_json = path / "vocab.json"
    if merges_txt.exists() and vocab_json.exists():
        return CLIPBpeTokenizer(str(vocab_json), str(merges_txt), do_lower_case=do_lower)

    # Unigram: .model file
    model_files = list(path.glob("*.model"))
    if model_files:
        return UnigramTokenizer(str(model_files[0]))

    # tokenizer.json (HuggingFace) — check Unigram before BPE
    tok_json = path / "tokenizer.json"
    if tok_json.exists():
        try:
            import json as _json
            with open(str(tok_json), "r", encoding="utf-8") as f:
                _tok_data = _json.load(f)
            _model_type = _tok_data.get("model", {}).get("type")
            if _model_type == "Unigram":
                return UnigramTokenizer.from_tokenizer_json(str(tok_json))
        except Exception:
            pass
        return _create_from_tokenizer_json(str(tok_json), do_lower_case=do_lower)

    return None


def _create_from_tokenizer_json(path: str, do_lower_case: bool = False) -> CLIPBpeTokenizer | None:
    """Try to create a CLIPBpeTokenizer from tokenizer.json.

    This is a best-effort fallback for HuggingFace models that only
    provide tokenizer.json (not individual merges.txt + vocab.json).
    """
    import json

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract the BPE model data from tokenizer.json
        model_data = data.get("model", {})
        vocab = model_data.get("vocab", {})
        merges = model_data.get("merges", [])

        if not vocab or not merges:
            # Try SentencePiece model from tokenizer.json
            import warnings
            warnings.warn("tokenizer.json found but no BPE vocab/merges; try UnigramTokenizer directly")
            return None

        # Write temporary files and load
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        vpath = os.path.join(tmpdir, "vocab.json")
        mpath = os.path.join(tmpdir, "merges.txt")

        with open(vpath, "w", encoding="utf-8") as f:
            json.dump(vocab, f, ensure_ascii=False)

        with open(mpath, "w", encoding="utf-8") as f:
            for line in merges:
                f.write(line + "\n")

        tokenizer = CLIPBpeTokenizer(vpath, mpath, do_lower_case=do_lower_case)
        return tokenizer
    except Exception:
        return None
