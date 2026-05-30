# rag/pdf_extractor.py
import os
import pdfplumber
from typing import List, Dict

# Thư mục chứa PDF
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "pdf")


def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Trích xuất text từ PDF, chia theo từng trang.
    Trả về list các dict: {page, text, source, ticker, period}
    """
    chunks = []

    # Lấy metadata từ tên file
    filename = os.path.basename(pdf_path)
    ticker, period = _parse_filename_metadata(filename)

    print(f"  PDF Extractor: Đọc file '{filename}'...")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"  PDF Extractor: {total_pages} trang")

            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and len(text.strip()) > 50:  # Bỏ trang gần trống
                    chunks.append({
                        "page":    i + 1,
                        "text":    text.strip(),
                        "source":  filename,
                        "ticker":  ticker,
                        "period":  period,
                        "doc_id":  f"{filename}_page_{i+1}"
                    })

        print(f"  PDF Extractor: Trích xuất {len(chunks)} trang có nội dung.")
        return chunks

    except Exception as e:
        print(f"  PDF Extractor: Lỗi khi đọc '{pdf_path}': {e}")
        return []


def extract_all_pdfs_in_reports_dir() -> List[Dict]:
    """Đọc tất cả PDF trong thư mục data/reports/"""
    all_chunks = []

    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        print(f"  PDF Extractor: Tạo thư mục '{REPORTS_DIR}'. Hãy đặt PDF vào đây.")
        return []

    pdf_files = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".pdf")]

    if not pdf_files:
        print(f"  PDF Extractor: Không tìm thấy PDF nào trong '{REPORTS_DIR}'.")
        return []

    print(f"  PDF Extractor: Tìm thấy {len(pdf_files)} PDF: {pdf_files}")

    for pdf_file in pdf_files:
        pdf_path = os.path.join(REPORTS_DIR, pdf_file)
        chunks = extract_text_from_pdf(pdf_path)
        all_chunks.extend(chunks)

    print(f"  PDF Extractor: Tổng cộng {len(all_chunks)} chunks từ tất cả PDF.")
    return all_chunks


def _parse_filename_metadata(filename: str):
    """
    Tự động đoán ticker và period từ tên file.
    Ví dụ: "10Q-Q1-2025-AAPL.pdf" → ("AAPL", "Q1 2025")
    Nếu không đoán được → dùng giá trị mặc định.
    """
    name = filename.replace(".pdf", "").upper()

    # Đoán ticker
    ticker = "UNKNOWN"
    known_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META",
                     "NVDA", "TSLA", "JPM", "V", "WMT"]
    for t in known_tickers:
        if t in name:
            ticker = t
            break

    # Đoán period
    period = "UNKNOWN"
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        if q in name:
            for year in ["2023", "2024", "2025", "2026"]:
                if year in name:
                    period = f"{q} {year}"
                    break
            break

    # Xử lý tên file cụ thể: 10Q-Q1-2025-as-filed.pdf, 10Q-Q2-2025-as-filed.pdf
    if "10Q" in name and "2025" in name:
        ticker = "AAPL"  # Cả 2 file đều là Apple
        if "Q1" in name:
            period = "Q1 2025"
        elif "Q2" in name:
            period = "Q2 2025"
        elif "Q3" in name:
            period = "Q3 2025"
        elif "Q4" in name:
            period = "Q4 2025"

    return ticker, period


if __name__ == "__main__":
    chunks = extract_all_pdfs_in_reports_dir()
    if chunks:
        print(f"\nSample chunk đầu tiên:")
        print(f"  Source: {chunks[0]['source']}")
        print(f"  Ticker: {chunks[0]['ticker']}")
        print(f"  Period: {chunks[0]['period']}")
        print(f"  Page:   {chunks[0]['page']}")
        print(f"  Text:   {chunks[0]['text'][:200]}...")