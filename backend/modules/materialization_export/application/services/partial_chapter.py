"""Extract only present JSON subobjects, preserving the final unclosed string."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Node:
    start: int
    end: int
    complete: bool
    kind: str
    value: object = None
    members: dict[str, Node] = field(default_factory=dict)
    elements: tuple[Node, ...] = ()


def capture_tree(text: str) -> Node:
    decoder = json.JSONDecoder()
    count = 0

    def white(pos: int) -> int:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        return pos

    def parse(pos: int, depth: int) -> Node:
        nonlocal count
        count += 1
        if depth > 24 or count > 4096:
            raise ValueError("PARTIAL_STRUCTURE_LIMIT")
        pos = white(pos)
        start = pos
        if pos >= len(text):
            return Node(pos, pos, False, "missing")
        if text[pos] == '"':
            try:
                value, end = decoder.raw_decode(text, pos)
                return Node(start, end, True, "string", value)
            except json.JSONDecodeError as error:
                if error.msg != "Unterminated string starting at":
                    raise ValueError("PARTIAL_STRUCTURE_REJECTED") from None
                return Node(start, len(text), False, "string")
        if text[pos] in "[{":
            obj = text[pos] == "{"
            close = "}" if obj else "]"
            members: dict[str, Node] = {}
            elements: list[Node] = []
            pos = white(pos + 1)
            while pos < len(text):
                if text[pos] == close:
                    return Node(start, pos + 1, True, "object" if obj else "array",
                        members=members, elements=tuple(elements))
                if obj:
                    key = parse(pos, depth + 1)
                    pos = white(key.end)
                    if (not key.complete or type(key.value) is not str
                            or key.value in members or pos >= len(text) or text[pos] != ":"):
                        raise ValueError("PARTIAL_STRUCTURE_REJECTED")
                    child = parse(pos + 1, depth + 1)
                    members[key.value] = child
                else:
                    child = parse(pos, depth + 1)
                    elements.append(child)
                pos = white(child.end)
                if not child.complete or pos >= len(text):
                    break
                if text[pos] == close:
                    continue
                if text[pos] != ",":
                    raise ValueError("PARTIAL_STRUCTURE_REJECTED")
                pos = white(pos + 1)
                if pos < len(text) and text[pos] == close:
                    raise ValueError("PARTIAL_STRUCTURE_REJECTED")
            return Node(start, len(text), False, "object" if obj else "array",
                members=members, elements=tuple(elements))
        try:
            value, end = decoder.raw_decode(text, pos)
            return Node(start, end, True, "scalar", value)
        except json.JSONDecodeError:
            raise ValueError("PARTIAL_STRUCTURE_REJECTED") from None

    root = parse(0, 0)
    if root.kind != "object" or root.complete or root.end != len(text):
        raise ValueError("PARTIAL_STRUCTURE_REJECTED")
    return root


def present(text: str, node: Node, kind: str) -> object:
    if not node.complete or node.kind != kind:
        raise ValueError("PARTIAL_REQUIRED_CONTENT_MISSING")
    return json.loads(text[node.start:node.end])
