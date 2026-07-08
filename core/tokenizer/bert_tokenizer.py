from .base import BaseTokenizer


class _TrieNode:
    __slots__ = ("children", "token_id", "is_subword")

    def __init__(self):
        self.children: dict[str, "_TrieNode"] = {}
        self.token_id: int | None = None
        self.is_subword: bool = False


class BertWordPieceTokenizer(BaseTokenizer):
    SPECIAL_TOKENS = {
        "[PAD]": 0,
        "[UNK]": 100,
        "[CLS]": 101,
        "[SEP]": 102,
        "[MASK]": 103,
    }

    def __init__(self, vocab_file: str | None = None, do_lower_case: bool = False):
        self.vocab: dict[str, int] = {}
        self.root = _TrieNode()
        self._unk_token = "[UNK]"
        self.do_lower_case = do_lower_case

        if vocab_file is not None:
            self._load(vocab_file)

    @property
    def bos_token_id(self) -> int:
        return self.SPECIAL_TOKENS["[CLS]"]

    @property
    def eos_token_id(self) -> int:
        return self.SPECIAL_TOKENS["[SEP]"]

    @property
    def pad_token_id(self) -> int:
        return self.SPECIAL_TOKENS["[PAD]"]

    def _load(self, vocab_file: str) -> None:
        """Load vocab.txt and build Trie."""
        with open(vocab_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                token = line.strip()
                self.vocab[token] = idx
                self._add_to_trie(token, idx)

        for name, tid in self.SPECIAL_TOKENS.items():
            if name not in self.vocab:
                self.vocab[name] = tid

    def _add_to_trie(self, token: str, token_id: int) -> None:
        """Insert a token into the Trie."""
        node = self.root
        for ch in token:
            if ch not in node.children:
                node.children[ch] = _TrieNode()
            node = node.children[ch]
        node.token_id = token_id
        node.is_subword = token.startswith("##")

    def _has_token(self, text: str) -> bool:
        """Check if text exists as a token in the trie (exact match)."""
        node = self.root
        for ch in text:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.token_id is not None

    def tokenize(self, text: str) -> list[str]:
        """Tokenize using greedy longest-match first (maximum matching)."""
        if not text:
            return []

        if self.do_lower_case:
            text = text.lower()

        text = self._clean_text(text)
        words = text.split()
        tokens = []
        for word in words:
            word_tokens = self._wordpiece_tokenize(word)
            tokens.extend(word_tokens)
        return tokens

    def _clean_text(self, text: str) -> str:
        """Clean text: strip control chars, normalize whitespace."""
        output = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD or self._is_control(ch):
                continue
            if self._is_whitespace(ch):
                output.append(" ")
            else:
                output.append(ch)
        return "".join(output)

    @staticmethod
    def _is_whitespace(ch: str) -> bool:
        """Check if char is whitespace."""
        if ch in (" ", "\t", "\n", "\r"):
            return True
        import unicodedata
        cat = unicodedata.category(ch)
        if cat == "Zs":
            return True
        return False

    @staticmethod
    def _is_control(ch: str) -> bool:
        """Check if char is a control character."""
        if ch in ("\t", "\n", "\r"):
            return False
        import unicodedata
        cat = unicodedata.category(ch)
        return cat in ("Cc", "Cf")

    def _wordpiece_tokenize(self, word: str) -> list[str]:
        """Tokenize a single word into word pieces.

        Greedy longest-match: start from beginning, find longest prefix
        that exists in vocab. If found, append and continue from where
        we left off. If not found, use [UNK] and advance by one char.
        """
        if not word:
            return []

        if self._has_token(word):
            return [word]

        tokens = []
        remaining = word
        while remaining:
            longest_match = None
            longest_len = 0
            node = self.root
            for i, ch in enumerate(remaining):
                if ch not in node.children:
                    break
                node = node.children[ch]
                if node.token_id is not None and not node.is_subword:
                    longest_match = remaining[: i + 1]
                    longest_len = i + 1

            if longest_match is None:
                node = self.root
                for i, ch in enumerate(remaining):
                    if ch not in node.children:
                        break
                    node = node.children[ch]
                    if node.token_id is not None:
                        token_str = remaining[: i + 1]
                        if i == 0 or remaining[0] in self.vocab:
                            pass
                        if not token_str.startswith("##"):
                            if i + 1 >= longest_len:
                                longest_match = token_str
                                longest_len = i + 1

            if longest_match is None:
                for i in range(len(remaining)):
                    prefix = remaining[: i + 1]
                    subword_prefix = "##" + remaining[: i + 1]
                    if prefix in self.vocab and i == 0:
                        longest_match = prefix
                        longest_len = i + 1
                        break
                    if subword_prefix in self.vocab:
                        longest_match = subword_prefix
                        longest_len = i + 1

            if longest_match is None:
                tokens.append(self._unk_token)
                remaining = remaining[1:]
            else:
                tokens.append(longest_match)
                remaining = remaining[longest_len:]

        return tokens

    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
        """Convert list of token strings to IDs.

        Unknown tokens are mapped to [UNK].
        """
        unk_id = self.vocab.get(self._unk_token, 100)
        return [self.vocab.get(t, unk_id) for t in tokens]

    def vocab_size(self) -> int:
        return len(self.vocab)
