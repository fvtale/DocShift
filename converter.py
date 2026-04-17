from pathlib import Path
from pdf2docx import Converter


def convert_pdf_to_docx(pdf_path: str, output_dir: str) -> str:
    pdf = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{pdf.stem}.docx"
    cv = Converter(str(pdf))
    try:
        cv.convert(str(output_path), start=0, end=None)
    finally:
        cv.close()
    return str(output_path)
