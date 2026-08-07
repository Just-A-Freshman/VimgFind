from __future__ import annotations

from abc import ABC, abstractmethod

class BaseTokenizer(ABC):
    vocab: dict[str, int]

    @abstractmethod
    def tokenize(self, text: str) -> list[str]:
        ...

    @abstractmethod
    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
        ...

    @abstractmethod
    def vocab_size(self) -> int:
        ...

    @property
    def bos_token_id(self) -> int | None:
        """Beginning-of-sequence token ID (e.g. [CLS]), or None if unused."""
        return None

    @property
    def eos_token_id(self) -> int | None:
        """End-of-sequence token ID (e.g. [SEP]), or None if unused."""
        return None

    @property
    def pad_token_id(self) -> int:
        """Padding token ID."""
        return 0

    def encode(self, text: str) -> list[int]:
        """Convenience: tokenize + convert_tokens_to_ids."""
        return self.convert_tokens_to_ids(self.tokenize(text))

    def decode(self, ids: list[int], skip_special: bool = False) -> str:
        """Convert token IDs back to string."""
        id_to_token = {v: k for k, v in self.vocab.items()}
        tokens = []
        for i in ids:
            token = id_to_token.get(i, "[UNK]")
            if skip_special and token.startswith("[") and token.endswith("]"):
                continue
            tokens.append(token)
        text = "".join(tokens)
        text = text.replace(" ##", "").replace("##", "")
        return text.strip()

    def __getitem__(self, token: str) -> int:
        """Allow dict-style access: tokenizer['[CLS]'] -> id."""
        return self.vocab[token]
