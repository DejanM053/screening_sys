"""Namespace-agnostic XML helpers — sanctions-list XML feeds vary in namespace usage."""
from __future__ import annotations

from xml.etree import ElementTree as ET


def local_tag(element: ET.Element) -> str:
    """Strip a `{namespace}` prefix from an element's tag."""
    tag = element.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def find_all_local(parent: ET.Element, tag_name: str) -> list[ET.Element]:
    return [child for child in parent.iter() if local_tag(child) is not None and local_tag(child) == tag_name and child is not parent]


def direct_children_local(parent: ET.Element, tag_name: str) -> list[ET.Element]:
    return [child for child in parent if local_tag(child) == tag_name]


def child_text(parent: ET.Element, tag_name: str) -> str | None:
    for child in parent:
        if local_tag(child) == tag_name:
            return (child.text or "").strip() or None
    return None
