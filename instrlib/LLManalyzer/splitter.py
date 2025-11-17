import csv
import pandas as pd
from pathlib import Path
from docx import Document
from odf.opendocument import load as load_odt
from odf.text import P
import subprocess

class Chunk:
    def __init__(self, index, text, metadata=None):
        self.index = index
        self.text = text
        self.metadata = metadata or {}

def split_txt(path):
    """Splits a text file into a single chunk."""
    text = Path(path).read_text(errors="ignore")
    return [Chunk(0, text)]

def split_csv(path):
    """Splits a CSV file into chunks, one per row."""
    chunks = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            chunks.append(Chunk(i, " ".join(row.values()), metadata=row))
    return chunks

def split_excel(path):
    """Splits an Excel file into chunks, one per row. Same as CSV."""
    chunks = []
    df = pd.read_excel(path)
    for i, row in df.iterrows():
        text = " ".join(str(x) for x in row.values)
        chunks.append(Chunk(i, text, metadata=row.to_dict()))
    return chunks

def split_docx(path):
    """Splits a DOCX file into chunks, one per paragraph."""
    doc = Document(path)
    chunks = []
    for i, para in enumerate(doc.paragraphs):
        if para.text.strip():
            chunks.append(Chunk(i, para.text))
    return chunks

def split_odt(path):
    """Splits an ODT file into chunks, one per paragraph. Same as DOCX."""
    chunks = []
    doc = load_odt(path)
    paras = doc.getElementsByType(P)
    for i, p in enumerate(paras):
        text = "".join(n.data for n in p.childNodes if hasattr(n, 'data'))
        chunks.append(Chunk(i, text))
    return chunks

def split_pdf(path):
    """Splits a PDF file into chunks, one per page."""
    out = subprocess.run(
        ["pdftotext", "-layout", path, "-"], 
        capture_output=True, text=True
    )
    pages = out.stdout.split("\f")

    # Remove ONLY the final extra empty page inserted by pdftotext
    if len(pages) > 0 and pages[-1].strip() == "":
        pages = pages[:-1]
    return [Chunk(i, p) for i, p in enumerate(pages)]

def split_file(path):
    ext = Path(path).suffix.lower()
    if ext == ".txt":
        return split_txt(path)
    if ext == ".csv":
        return split_csv(path)
    if ext in [".xls", ".xlsx"]:
        return split_excel(path)
    if ext == ".docx":
        return split_docx(path)
    if ext == ".odt":
        return split_odt(path)
    if ext == ".pdf":
        return split_pdf(path)
    raise ValueError(f"Unsupported file type: {ext}")
