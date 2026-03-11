from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


def extract_paragraphs(xml_path: Path) -> list[str]:
    if not xml_path.exists():
        return []
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    paras = []
    for p in root.findall(".//tei:p", ns):
        text = "".join(p.itertext()).strip()
        if text:
            paras.append(text)
    return paras
