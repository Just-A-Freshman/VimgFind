"""Unigram tokenizer (pure Python, minimal protobuf parser + Viterbi DP).

Loads SentencePiece .model files and decodes using the Unigram
language model: Viterbi algorithm finds the highest-probability
segmentation path.

No protobuf library dependency — uses a minimal wire format parser.
"""

import math
import struct
from .base import BaseTokenizer


# ---------------------------------------------------------------------------
# Minimal protobuf wire format reader
# ---------------------------------------------------------------------------

class _ProtoReader:
    """Read protobuf fields from a bytes buffer."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def eof(self) -> bool:
        return self.pos >= len(self.data)

    def _read_varint(self) -> int:
        value = 0
        shift = 0
        while True:
            byte = self.data[self.pos]
            self.pos += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
        return value

    def _read_fixed32(self) -> float:
        val = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return val

    def _read_bytes(self, length: int) -> bytes:
        result = self.data[self.pos : self.pos + length]
        self.pos += length
        return result

    def read_message(self) -> list[tuple[int, int, bytes]]:
        """Read all fields as (field_number, wire_type, raw_value_bytes).

        Use parse helpers to interpret the raw bytes.
        """
        fields: list[tuple[int, int, bytes]] = []
        while self.pos < len(self.data):
            tag = self._read_varint()
            field_number = tag >> 3
            wire_type = tag & 0x7

            if wire_type == 0:  # varint
                val_start = self.pos
                self._read_varint()
                val_bytes = self.data[val_start : self.pos]
                fields.append((field_number, wire_type, val_bytes))
            elif wire_type == 2:  # length-delimited
                length = self._read_varint()
                raw = self._read_bytes(length)
                fields.append((field_number, wire_type, raw))
            elif wire_type == 5:  # fixed32
                raw = self._read_bytes(4)
                fields.append((field_number, wire_type, raw))
            elif wire_type == 1:  # fixed64
                raw = self._read_bytes(8)
                fields.append((field_number, wire_type, raw))
            else:
                raise ValueError(f"Unknown wire type {wire_type} at pos {self.pos}")
        return fields

    @staticmethod
    def varint_value(raw: bytes) -> int:
        val = 0
        shift = 0
        for byte in raw:
            val |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
        return val

    @staticmethod
    def fixed32_value(raw: bytes) -> float:
        return struct.unpack("<f", raw)[0]


# ---------------------------------------------------------------------------
# Trie for fast prefix matching
# ---------------------------------------------------------------------------

class _TrieNode:
    __slots__ = ("children", "score", "token_id", "token_type")

    def __init__(self):
        self.children: dict[str, "_TrieNode"] = {}
        self.score: float | None = None
        self.token_id: int | None = None
        self.token_type: int = 1  # default NORMAL


class _UnigramTrie:
    """Trie containing all pieces with their scores."""

    def __init__(self):
        self.root = _TrieNode()
        self.max_token_len = 0

    def insert(self, token: str, token_id: int, score: float, token_type: int) -> None:
        node = self.root
        for ch in token:
            if ch not in node.children:
                node.children[ch] = _TrieNode()
            node = node.children[ch]
        node.score = score
        node.token_id = token_id
        node.token_type = token_type
        if len(token) > self.max_token_len:
            self.max_token_len = len(token)

    def prefixes(self, text: str, start: int) -> list[tuple[int, int, float]]:
        """Return all matching token (end_pos, token_id, score) starting at `start`."""
        node = self.root
        results: list[tuple[int, int, float]] = []
        i = start
        while i < len(text) and text[i] in node.children:
            node = node.children[text[i]]
            i += 1
            if node.token_id is not None:
                results.append((i, node.token_id, node.score or 0.0))
        return results


# ---------------------------------------------------------------------------
# SentencePiece normalization helpers
# ---------------------------------------------------------------------------

def _sentencepiece_normalize(text: str, add_dummy_prefix: bool,
                               remove_extra_whitespaces: bool,
                               escape_whitespaces: bool) -> str:
    """Apply basic SentencePiece normalization."""
    if remove_extra_whitespaces:
        text = " ".join(text.split())
    if add_dummy_prefix and not text.startswith(" "):
        text = " " + text
    if escape_whitespaces:
        text = text.replace(" ", "▁")
    import unicodedata
    text = unicodedata.normalize("NFKC", text)
    return text


# ---------------------------------------------------------------------------
# Byte-piece handling for SentencePiece
# ---------------------------------------------------------------------------

def _is_byte_piece(piece: str) -> bool:
    """Check if piece is a byte piece like '<0xXX>'."""
    return piece.startswith("<0x") and piece.endswith(">") and len(piece) == 6


def _byte_piece_to_char(piece: str) -> str:
    """Convert '<0xXX>' to the actual byte character."""
    byte_val = int(piece[3:5], 16)
    return chr(byte_val)


# ---------------------------------------------------------------------------
# Main UnigramTokenizer
# ---------------------------------------------------------------------------

class UnigramTokenizer(BaseTokenizer):
    """Unigram tokenizer loaded from SentencePiece .model file.

    Uses Viterbi DP for optimal segmentation.
    """

    def __init__(self, model_file: str | None = None):
        self.vocab: dict[str, int] = {}
        self.trie = _UnigramTrie()
        self._decoder: dict[int, str] = {}
        self._scores: dict[int, float] = {}

        # Normalization config (from model)
        self._add_dummy_prefix = True
        self._remove_extra_whitespaces = True
        self._escape_whitespaces = True

        # Special piece info
        self._control_tokens: set[int] = set()
        self._byte_tokens: set[int] = set()
        self._unk_token = "<unk>"
        self._unk_id = 0

        if model_file is not None:
            self._load(model_file)

    def _load(self, model_file: str) -> None:
        """Parse SentencePiece .model protobuf and build vocabulary."""
        with open(model_file, "rb") as f:
            data = f.read()

        # The model file starts with a varint length for the outer message
        reader = _ProtoReader(data)
        _ = reader._read_varint()  # outer message length

        # Parse top-level SentencePieceModel
        outer_reader = _ProtoReader(data[reader.pos:])

        for field_number, wire_type, raw in outer_reader.read_message():
            if field_number == 1:  # trainer_spec
                self._parse_trainer_spec(raw)
            elif field_number == 2:  # normalizer_spec
                self._parse_normalizer_spec(raw)
            elif field_number == 3:  # pieces (repeated)
                self._parse_piece(raw)

    def _parse_trainer_spec(self, raw: bytes) -> None:
        """Parse trainer_spec sub-message (just check model_type)."""
        reader = _ProtoReader(raw)
        for field_number, wire_type, raw_val in reader.read_message():
            if field_number == 3 and wire_type == 0:  # model_type
                mt = _ProtoReader.varint_value(raw_val)
                # model_type: 1 = UNIGRAM, 2 = BPE
                if mt == 2:
                    import warnings
                    warnings.warn(
                        "Model type is BPE, not Unigram. SentencePiece BPE "
                        "models are loaded but Viterbi may not be optimal."
                    )

    def _parse_normalizer_spec(self, raw: bytes) -> None:
        """Parse normalizer_spec for flags."""
        reader = _ProtoReader(raw)
        for field_number, wire_type, raw_val in reader.read_message():
            if wire_type == 0:  # varint (bool)
                val = _ProtoReader.varint_value(raw_val)
                if field_number == 3:  # add_dummy_prefix
                    self._add_dummy_prefix = bool(val)
                elif field_number == 4:  # remove_extra_whitespaces
                    self._remove_extra_whitespaces = bool(val)
                elif field_number == 5:  # escape_whitespaces
                    self._escape_whitespaces = bool(val)

    def _parse_piece(self, raw: bytes) -> None:
        """Parse a single SentencePiece piece."""
        reader = _ProtoReader(raw)
        piece_str = ""
        score = 0.0
        ptype = 1  # NORMAL

        for field_number, wire_type, raw_val in reader.read_message():
            if field_number == 1 and wire_type == 2:  # piece (string)
                # raw_val is already the string bytes
                piece_str = raw_val.decode("utf-8", errors="replace")
            elif field_number == 2 and wire_type == 5:  # score (float)
                score = _ProtoReader.fixed32_value(raw_val)
            elif field_number == 3 and wire_type == 0:  # type (enum)
                ptype = _ProtoReader.varint_value(raw_val)

        if not piece_str:
            return

        token_id = len(self.vocab)
        actual_piece = piece_str

        if ptype == 6:  # BYTE
            self._byte_tokens.add(token_id)
            if _is_byte_piece(piece_str):
                actual_piece = _byte_piece_to_char(piece_str)
        elif ptype == 3:  # CONTROL
            self._control_tokens.add(token_id)
        elif ptype == 4:  # USER_DEFINED
            pass

        # Check if this is the UNK token
        if piece_str == "<unk>":
            self._unk_id = token_id

        self.vocab[actual_piece] = token_id
        self._decoder[token_id] = piece_str
        self._scores[token_id] = score

        # Insert into Trie (for unk/control/byte pieces, score is irrelevant)
        self.trie.insert(actual_piece, token_id, score, ptype)

        # Also handle byte pieces in the trie by their actual character
        if _is_byte_piece(piece_str):
            byte_char = _byte_piece_to_char(piece_str)
            if byte_char != actual_piece:
                self.trie.insert(byte_char, token_id, score, ptype)

    # ------------------------------------------------------------------
    # Viterbi decoding
    # ------------------------------------------------------------------

    def _viterbi(self, text: str) -> list[int]:
        """Run Viterbi algorithm to find optimal segmentation.

        Returns list of token IDs for the highest-probability path.
        """
        n = len(text)
        if n == 0:
            return []

        # dp[i] = best log prob up to position i
        # back[i] = (start_j, token_id) for the best token ending at i
        neg_inf = -float("inf")
        dp = [neg_inf] * (n + 1)
        dp[0] = 0.0
        back: list[tuple[int, int] | None] = [None] * (n + 1)

        for i in range(n):
            if dp[i] == neg_inf:
                continue

            # Find all tokens starting at position i
            for end_pos, token_id, score in self.trie.prefixes(text, i):
                # Score is the SentencePiece unigram log probability
                candidate = dp[i] + score
                if candidate > dp[end_pos]:
                    dp[end_pos] = candidate
                    back[end_pos] = (i, token_id)

            # Also try single character as fallback (UNK)
            if back[i + 1] is None:
                # Check if the single char is a known token (byte fallback)
                ch = text[i]
                if ch in self.vocab:
                    tid = self.vocab[ch]
                    score = self._scores.get(tid, -10.0)
                    dp[i + 1] = dp[i] + score
                    back[i + 1] = (i, tid)
                else:
                    dp[i + 1] = dp[i] + self._scores.get(self._unk_id, -10.0)
                    back[i + 1] = (i, self._unk_id)

        # Backtrack
        ids: list[int] = []
        pos = n
        while pos > 0:
            entry = back[pos]
            if entry is None:
                break
            start, tid = entry
            ids.append(tid)
            pos = start

        ids.reverse()
        return ids

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text into subword tokens."""
        normalized = _sentencepiece_normalize(
            text,
            self._add_dummy_prefix,
            self._remove_extra_whitespaces,
            self._escape_whitespaces,
        )
        ids = self._viterbi(normalized)
        return [self._decoder.get(i, self._unk_token) for i in ids]

    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs (Viterbi optimal path)."""
        normalized = _sentencepiece_normalize(
            text,
            self._add_dummy_prefix,
            self._remove_extra_whitespaces,
            self._escape_whitespaces,
        )
        return self._viterbi(normalized)

    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
        return [self.vocab.get(t, self._unk_id) for t in tokens]

    def decode(self, ids: list[int], skip_special: bool = False) -> str:
        id_to_token = self._decoder
        tokens = []
        for i in ids:
            if skip_special and i in self._control_tokens:
                continue
            token = id_to_token.get(i, self._unk_token)
            if _is_byte_piece(token):
                tokens.append(_byte_piece_to_char(token))
            elif token.startswith("▁"):
                tokens.append(" " + token[1:])
            else:
                tokens.append(token)
        text = "".join(tokens)
        if self._escape_whitespaces:
            text = text.replace("▁", " ")
        # Collapse the dummy prefix space (but keep actual spaces)
        if self._add_dummy_prefix and text.startswith(" "):
            text = text[1:]
        return text.strip()

    def vocab_size(self) -> int:
        return len(self.vocab)
