import json
import re
from .base import BaseTokenizer


def _bytes_to_unicode() -> tuple[dict[int, str], dict[str, int]]:
    """Map each byte 0-255 to a unique printable unicode char and vice versa."""
    bs: list[int] = (
        list(range(ord("!"), ord("~") + 1))   # 33-126
        + list(range(ord("¡"), ord("¬") + 1))  # 161-172
        + list(range(ord("®"), ord("ÿ") + 1))  # 174-255
    )
    cs: list[int] = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    encoder = {b: chr(c) for b, c in zip(bs, cs)}
    decoder = {chr(c): b for b, c in zip(bs, cs)}
    return encoder, decoder


_CLIP_PRETOKENIZE = re.compile(
    r"""<\|startoftext\|>|<\|endoftext\|>|'s|'t|'re|'ve|'m|'ll|'d|[\w]+|\d+|[^\s\w\d]+""",
    re.UNICODE,
)


class CLIPBpeTokenizer(BaseTokenizer):
    """BPE tokenizer compatible with OpenAI CLIP / GPT-2.

    Loads from:
      - vocab.json   (token → id mapping)
      - merges.txt   (BPE merge operations in priority order)

    Special tokens (CLIP hardcoded):
      <|startoftext|> = 49406
      <|endoftext|>   = 49407
    """

    SPECIAL_TOKENS: dict[str, int] = {
        "<|startoftext|>": 49406,
        "<|endoftext|>": 49407,
    }

    def __init__(
        self,
        vocab_file: str | None = None,
        merges_file: str | None = None,
        do_lower_case: bool = True,
    ):
        self.byte_encoder, self.byte_decoder = _bytes_to_unicode()
        self.vocab: dict[str, int] = {}
        self.bpe_ranks: dict[tuple[str, str], int] = {}
        self._decoder: dict[int, str] = {}
        self.do_lower_case = do_lower_case

        if vocab_file is not None:
            self._load_vocab(vocab_file)
        if merges_file is not None:
            self._load_merges(merges_file)

    @property
    def bos_token_id(self) -> int:
        return self.SPECIAL_TOKENS["<|startoftext|>"]

    @property
    def eos_token_id(self) -> int:
        return self.SPECIAL_TOKENS["<|endoftext|>"]

    @property
    def pad_token_id(self) -> int:
        return self.SPECIAL_TOKENS["<|endoftext|>"]

    def _load_vocab(self, vocab_file: str) -> None:
        """Load vocab.json."""
        with open(vocab_file, "r", encoding="utf-8") as f:
            self.vocab = json.load(f)

        for name, tid in self.SPECIAL_TOKENS.items():
            if name not in self.vocab:
                self.vocab[name] = tid

        self._decoder = {v: k for k, v in self.vocab.items()}

    def _load_merges(self, merges_file: str) -> None:
        """Load merges.txt and build bpe_ranks table.

        Each line in merges.txt: "token_a token_b"
        Line number = rank (lower = merged earlier = higher priority).
        """
        with open(merges_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        if lines and lines[0].startswith("#version"):
            lines = lines[1:]

        for rank, line in enumerate(lines):
            parts = line.split()
            if len(parts) != 2:
                continue
            self.bpe_ranks[(parts[0], parts[1])] = rank

    def _pretokenize(self, text: str) -> list[str]:
        """Split text into "words" pre-BPE using CLIP-style regex."""
        return _CLIP_PRETOKENIZE.findall(text)

    def _get_pairs(self, word: list[str]) -> set[tuple[str, str]]:
        """Return set of adjacent symbol pairs in a word."""
        return {(word[i], word[i + 1]) for i in range(len(word) - 1)}

    def _bpe_merge(self, token: str | list[str]) -> list[str]:
        """Apply BPE merges to a single pre-tokenized string or list of chars."""
        if isinstance(token, str):
            word = list(token)
        else:
            word = list(token)  # copy

        while len(word) > 1:
            pairs = self._get_pairs(word)
            if not pairs:
                break

            best_pair = None
            best_rank = float("inf")
            for pair in pairs:
                rank = self.bpe_ranks.get(pair, float("inf"))
                if rank < best_rank:
                    best_rank = rank
                    best_pair = pair

            if best_pair is None or best_rank == float("inf"):
                break

            first, second = best_pair
            new_word: list[str] = []
            i = 0
            while i < len(word):
                if (
                    i < len(word) - 1
                    and word[i] == first
                    and word[i + 1] == second
                ):
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            word = new_word

        return word

    def _encode_word(self, word: str) -> str:
        """Byte-encode a word: UTF-8 bytes → unicode chars via byte_encoder."""
        return "".join(self.byte_encoder[b] for b in word.encode("utf-8"))

    def tokenize(self, text: str) -> list[str]:
        """Full tokenize: lowercase → pretokenize → byte-encode → BPE → flatten.

        对每个预分词的 word，将最后一个 byte-encoded 字符添加 </w> 后缀，
        以标记词边界。不保留前导空格（与 HuggingFace CLIP 实现一致）。
        """
        if self.do_lower_case:
            text = text.lower()
        words = self._pretokenize(text)
        tokens: list[str] = []
        for word in words:
            if not word:
                continue
            encoded = self._encode_word(word)
            # 最后一个字符带上 </w> 词尾标记
            chars = list(encoded)
            chars[-1] = chars[-1] + "</w>"
            bpe_tokens = self._bpe_merge(chars)
            tokens.extend(bpe_tokens)
        return tokens

    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs (including BPE)."""
        tokens = self.tokenize(text)
        return self.convert_tokens_to_ids(tokens)

    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
        unk_id = self.vocab.get("<|endoftext|>", 0)
        return [self.vocab.get(t, unk_id) for t in tokens]

    def decode(self, ids: list[int], skip_special: bool = False) -> str:
        """Decode token IDs back to text (inverse of encode).

        Byte-encoded tokens are converted back through byte_decoder,
        then decoded as UTF-8. Special tokens like <|endoftext|> are
        returned as-is (or omitted if skip_special=True).
        """
        tokens = []
        for i in ids:
            token = self._decoder.get(i, "")
            if skip_special and token in self.SPECIAL_TOKENS:
                continue
            if token in self.SPECIAL_TOKENS:
                tokens.append(token)
                continue
            byte_chars = []
            for ch in token:
                byte_chars.append(self.byte_decoder.get(ch, 0))
            tokens.append(bytes(byte_chars).decode("utf-8", errors="replace"))
        return "".join(tokens)

    def vocab_size(self) -> int:
        return len(self.vocab)
