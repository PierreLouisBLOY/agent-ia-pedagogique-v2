"""Serialize one OPC namespace without changing ElementTree's global registry."""
from xml.etree.ElementTree import Element

from backend.adapters.outbound.export.word import _xml


def opc_xml(root: Element, namespace: str, *, error_code: str = "OPC_XML_NAMESPACE") -> bytes:
    prefix = "{" + namespace + "}"

    def local(node: Element) -> Element:
        if not node.tag.startswith(prefix):
            raise ValueError(error_code)
        result = Element(node.tag[len(prefix):], dict(node.attrib))
        result.text, result.tail = node.text, node.tail
        result.extend(local(child) for child in node)
        return result

    normalized = local(root)
    normalized.set("xmlns", namespace)
    return _xml(normalized)
