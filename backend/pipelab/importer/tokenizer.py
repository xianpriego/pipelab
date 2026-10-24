"""Tokenizer for ``gst-launch-1.0`` pipeline descriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

TokenKind = Literal["word", "link", "open", "close"]

_LAUNCHERS = ("gst-launch-1.0", "gst-launch")
_MIME_PREFIX = re.compile(r"^[A-Za-z0-9\-]+/[A-Za-z0-9_.+\-]+")


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str = ""
    quoted: bool = False  # the whole word was a quoted string


class _Scanner:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.tokens: list[Token] = []
        self.word: list[str] = []
        self.quoted_start = False

    def flush(self) -> None:
        if not self.word:
            return
        text = "".join(self.word)
        self.word = []
        quoted, self.quoted_start = self.quoted_start, False
        if not quoted:
            self._emit_word(text)
        else:
            self.tokens.append(Token("word", text, quoted=True))

    def _emit_word(self, text: str) -> None:
        if text == "(" or text.endswith(".("):
            self.tokens.append(Token("open"))
            return
        if text == ")":
            self.tokens.append(Token("close"))
            return
        while text.startswith("(") and text.count("(") > text.count(")"):
            self.tokens.append(Token("open"))
            text = text[1:]
        closing = 0
        while text.endswith(")") and text.count(")") > text.count("("):
            text, closing = text[:-1], closing + 1
        if text:
            self.tokens.append(Token("word", text))
        self.tokens.extend(Token("close") for _ in range(closing))

    def quoted(self, quote: str) -> None:
        if not self.word:
            self.quoted_start = True
        self.pos += 1
        while self.pos < len(self.text) and self.text[self.pos] != quote:
            char = self.text[self.pos]
            if char == "\\" and quote == '"' and self.pos + 1 < len(self.text):
                self.pos += 1
                char = self.text[self.pos]
            self.word.append(char)
            self.pos += 1
        self.pos += 1

    def run(self) -> list[Token]:
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\" and self.pos + 1 < len(self.text):
                following = self.text[self.pos + 1]
                if following == "\n":
                    self.flush()
                else:
                    self.word.append(following)
                self.pos += 2
            elif char.isspace():
                self.flush()
                self.pos += 1
            elif char == "!":
                self.flush()
                self.tokens.append(Token("link"))
                self.pos += 1
            elif char in "\"'":
                self.quoted(char)
            else:
                if self.word and self.quoted_start:
                    self.quoted_start = False
                self.word.append(char)
                self.pos += 1
        self.flush()
        return self.tokens


def looks_like_caps(text: str) -> bool:
    return bool(_MIME_PREFIX.match(text)) and "://" not in text


def _merge_split_caps(tokens: list[Token]) -> list[Token]:
    """``video/x-raw, width=640`` written without quotes arrives as several words."""
    merged: list[Token] = []
    for token in tokens:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and token.kind == "word"
            and previous.kind == "word"
            and looks_like_caps(previous.text)
            and previous.text.rstrip().endswith(",")
        ):
            merged[-1] = Token("word", f"{previous.text} {token.text}", previous.quoted)
        else:
            merged.append(token)
    return merged


def _strip_launcher(tokens: list[Token]) -> list[Token]:
    """Drop a leading ``gst-launch-1.0`` and its command line flags."""
    index = 0
    if tokens and tokens[0].kind == "word" and tokens[0].text.rsplit("/", 1)[-1] in _LAUNCHERS:
        index = 1
        while index < len(tokens) and tokens[index].kind == "word" and tokens[index].text.startswith("-"):
            index += 1
    return tokens[index:]


def tokenize(description: str) -> list[Token]:
    return _merge_split_caps(_strip_launcher(_Scanner(description).run()))
