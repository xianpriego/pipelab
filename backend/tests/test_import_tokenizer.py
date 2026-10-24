"""gst-launch tokenizer and parser (no catalog needed)."""

from __future__ import annotations

from pipelab.importer.parser import CapsItem, ElementItem, RefItem, parse
from pipelab.importer.tokenizer import Token, tokenize


def words(description: str) -> list[str]:
    return [t.text if t.kind == "word" else t.kind for t in tokenize(description)]


def test_links_with_and_without_spaces():
    assert words("a ! b!c") == ["a", "link", "b", "link", "c"]


def test_double_and_single_quotes():
    tokens = tokenize('filesink location="my \\"best\\" file.mp4" name=\'out put\'')
    assert [t.text for t in tokens] == ["filesink", 'location=my "best" file.mp4', "name=out put"]
    assert not any(t.quoted for t in tokens)


def test_fully_quoted_word_is_marked():
    assert tokenize('"video/x-raw, width=640"') == [Token("word", "video/x-raw, width=640", quoted=True)]


def test_unquoted_caps_with_spaces_are_merged():
    assert words("a ! video/x-raw, width=640, height=480 ! b") == [
        "a",
        "link",
        "video/x-raw, width=640, height=480",
        "link",
        "b",
    ]


def test_parentheses_inside_caps_are_not_bins():
    assert words("a ! video/x-raw(memory:CUDAMemory),format=(string)NV12 ! b")[2] == (
        "video/x-raw(memory:CUDAMemory),format=(string)NV12"
    )


def test_bins_are_tokenized():
    assert words("( a ! b )") == ["open", "a", "link", "b", "close"]
    assert words("bin.( a ) c") == ["open", "a", "close", "c"]
    assert words("(a ! b)") == ["open", "a", "link", "b", "close"]


def test_launcher_flags_and_continuations_are_removed():
    assert words("gst-launch-1.0 -e -v --gst-debug=*:3 a \\\n ! b") == ["a", "link", "b"]
    assert words("/usr/bin/gst-launch-1.0 a") == ["a"]


def test_parse_declarations_and_properties():
    parsed = parse(
        tokenize("videotestsrc name=src is-live=true ! comp.sink_1 compositor name=comp sink_1::xpos=3")
    )
    source, reference, compositor = parsed.items
    assert source == ElementItem("videotestsrc", "src", {"is-live": "true"})
    assert reference == RefItem("comp", "sink_1")
    assert compositor == ElementItem("compositor", "comp", {}, {"sink_1": {"xpos": "3"}})
    assert parsed.links == [(0, 1)]


def test_parse_caps_and_references_without_pad():
    parsed = parse(tokenize("a ! video/x-raw ! t. t. ! b"))
    assert parsed.items[1] == CapsItem("video/x-raw")
    assert parsed.items[2] == RefItem("t", None)
    assert parsed.links == [(0, 1), (1, 2), (3, 4)]


def test_parse_warnings():
    parsed = parse(tokenize("file:///x.mp4 ! decodebin ! foo=1 ! sink !"))
    assert parsed.items[0] is None
    assert any("URI" in w for w in parsed.warnings)
    assert any("foo=1" in w for w in parsed.warnings)
    assert any("dangling" in w for w in parsed.warnings)
