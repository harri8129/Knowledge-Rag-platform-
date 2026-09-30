from pathlib import Path

from pypdf import PdfReader

class ExtractionError(Exception):
      """Raised when document test cannot be extracted"""

def extract_pdf(file_obj):
    try:
        reader = PdfReader(file_obj)
       
        if reader.is_encrypted:
            raise ExtractionError(
                 "Encrypted PDFs are not supported"
                )  
        
        pages = []

        for page_number, page in enumerate(reader.pages, start = 1):
            text = page.extract_text() or ""

            pages.append({
                "page_number": page_number,
                "content": text.strip(),
            }) 

        if not any(page["content"] for page in pages):
            raise ExtractionError(
                "No Exception text found."
                "This may be a scanned PDF requiring OCR."
            )

        return pages

    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(
            f"Could not read PDF: {exc}"
        ) from exc


def extract_text_file(file_obj):

    try:
        content = file_obj.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            "Text file must use UTF-8 encoding."
        ) from exc 

    except Exception as exc:
        raise ExtractionError(
            f"Could not read text file: {exc}"
        ) from exc 

    if not content.strip():
        raise ExtractionError("The document is empty.")

    return [{
        "page_number": 1,
        "content": content.strip()
    }]

def extract_document(file_obj,file_type):

    if file_type == "pdf":
        return extract_pdf(file_obj)

    if file_type in ("txt","markdown"):
        return extract_text_file(file_obj)

    raise ExtractionError(
        f"Unsupported document type: {file_type}"
    )
