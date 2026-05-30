# rag/rag_handler.py
from typing import Dict, Any, List, Optional
from rag.pdf_extractor import extract_all_pdfs_in_reports_dir
from rag.chroma_store import add_documents, search_documents, get_stats

# Tự động ingest PDF khi module được import lần đầu
_initialized = False


def _ensure_initialized():
    """Ingest PDF vào ChromaDB nếu chưa làm."""
    global _initialized
    if _initialized:
        return

    stats = get_stats()
    if stats["total_documents"] == 0:
        print("  RAG Handler: ChromaDB trống, bắt đầu ingest PDF...")
        chunks = extract_all_pdfs_in_reports_dir()
        if chunks:
            add_documents(chunks)
        else:
            print("  RAG Handler: Không có PDF nào để ingest.")
    else:
        print(f"  RAG Handler: ChromaDB đã có {stats['total_documents']} documents. "
              f"Tickers: {stats['tickers']}, Periods: {stats['periods']}")

    _initialized = True


def search_reports(
    query: str,
    ticker: Optional[str] = None,
    period: Optional[str] = None,
    n_results: int = 5
) -> Dict[str, Any]:
    """
    Tìm kiếm thông tin trong báo cáo tài chính PDF.

    Args:
        query: Câu hỏi của user
        ticker: Mã cổ phiếu (e.g. "AAPL")
        period: Kỳ báo cáo (e.g. "Q1 2025")
        n_results: Số kết quả trả về

    Returns:
        Dict với status và danh sách kết quả
    """
    _ensure_initialized()

    print(f"  RAG Handler: Tìm kiếm — query='{query[:60]}', "
          f"ticker={ticker}, period={period}")

    results = search_documents(
        query=query,
        ticker=ticker,
        period=period,
        n_results=n_results
    )

    if not results:
        # Thử lại không có filter nếu không tìm thấy
        if ticker or period:
            print("  RAG Handler: Không tìm thấy với filter, thử lại không filter...")
            results = search_documents(query=query, n_results=n_results)

    if not results:
        return {
            "status": "no_results",
            "query": query,
            "results": [],
            "context_text": "Không tìm thấy thông tin liên quan trong báo cáo tài chính."
        }

    # Tạo context text để truyền vào LLM
    context_parts = []
    for i, r in enumerate(results, 1):
        context_parts.append(
            f"[Nguồn {i}: {r['source']}, Trang {r['page']}, "
            f"Ticker: {r['ticker']}, Kỳ: {r['period']}]\n{r['text']}"
        )
    context_text = "\n\n---\n\n".join(context_parts)

    return {
        "status": "success",
        "query": query,
        "results": results,
        "context_text": context_text,
        "sources": list(set(r["source"] for r in results))
    }


def ingest_new_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Thêm một PDF mới vào ChromaDB.
    Dùng khi user upload thêm báo cáo mới.
    """
    from rag.pdf_extractor import extract_text_from_pdf
    chunks = extract_text_from_pdf(pdf_path)
    if not chunks:
        return {"status": "error", "message": "Không trích xuất được text từ PDF."}

    add_documents(chunks)
    return {
        "status": "success",
        "chunks_added": len(chunks),
        "ticker": chunks[0]["ticker"] if chunks else None,
        "period": chunks[0]["period"] if chunks else None
    }


def get_rag_stats() -> Dict:
    """Trả về thống kê RAG module."""
    return get_stats()


if __name__ == "__main__":
    import json
    print("=== Test RAG Handler ===")

    # Test tìm kiếm
    result = search_reports(
        query="What is Apple's total revenue in Q1 2025?",
        ticker="AAPL",
        period="Q1 2025"
    )

    print(f"\nStatus: {result['status']}")
    print(f"Sources: {result.get('sources', [])}")
    if result["results"]:
        print(f"\nTop result (page {result['results'][0]['page']}):")
        print(result["results"][0]["text"][:300])