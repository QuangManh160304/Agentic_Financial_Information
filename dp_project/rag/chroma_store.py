# rag/chroma_store.py
import os
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma_db")
COLLECTION_NAME = "financial_reports"

# Dùng embedding mặc định của ChromaDB (không cần API key)
# Nếu muốn dùng OpenAI embedding thì thay bằng OpenAIEmbeddingFunction
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()

_client = None
_collection = None


def _get_collection():
    """Khởi tạo ChromaDB client và collection (lazy init)."""
    global _client, _collection

    if _collection is not None:
        return _collection

    os.makedirs(CHROMA_DIR, exist_ok=True)

    _client = chromadb.PersistentClient(path=CHROMA_DIR)
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"  ChromaDB: Collection '{COLLECTION_NAME}' sẵn sàng "
          f"({_collection.count()} documents).")
    return _collection


def add_documents(chunks: List[Dict]) -> None:
    """
    Thêm các chunks PDF vào ChromaDB.
    Tự động bỏ qua doc_id đã tồn tại (idempotent).
    """
    collection = _get_collection()

    if not chunks:
        print("  ChromaDB: Không có chunks để thêm.")
        return

    # Lấy danh sách ID đã có
    existing = set(collection.get()["ids"])

    new_chunks = [c for c in chunks if c["doc_id"] not in existing]

    if not new_chunks:
        print(f"  ChromaDB: Tất cả {len(chunks)} chunks đã tồn tại, bỏ qua.")
        return

    ids       = [c["doc_id"] for c in new_chunks]
    documents = [c["text"]   for c in new_chunks]
    metadatas = [{
        "source": c["source"],
        "ticker": c["ticker"],
        "period": c["period"],
        "page":   str(c["page"])
    } for c in new_chunks]

    # ChromaDB giới hạn batch size
    BATCH_SIZE = 100
    for i in range(0, len(ids), BATCH_SIZE):
        collection.add(
            ids=ids[i:i+BATCH_SIZE],
            documents=documents[i:i+BATCH_SIZE],
            metadatas=metadatas[i:i+BATCH_SIZE]
        )

    print(f"  ChromaDB: Đã thêm {len(new_chunks)} chunks mới "
          f"(tổng: {collection.count()}).")


def search_documents(
    query: str,
    ticker: Optional[str] = None,
    period: Optional[str] = None,
    n_results: int = 5
) -> List[Dict]:
    """
    Tìm kiếm các đoạn văn bản liên quan đến câu hỏi.
    Có thể lọc theo ticker và/hoặc period.
    """
    collection = _get_collection()

    if collection.count() == 0:
        print("  ChromaDB: Không có documents nào. Hãy ingest PDF trước.")
        return []

    # Xây dựng filter
    where = {}
    if ticker and period:
        where = {"$and": [{"ticker": ticker}, {"period": period}]}
    elif ticker:
        where = {"ticker": ticker}
    elif period:
        where = {"period": period}

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )

        # Format kết quả
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "text":     results["documents"][0][i],
                "source":   results["metadatas"][0][i]["source"],
                "ticker":   results["metadatas"][0][i]["ticker"],
                "period":   results["metadatas"][0][i]["period"],
                "page":     results["metadatas"][0][i]["page"],
                "score":    1 - results["distances"][0][i]  # cosine similarity
            })

        print(f"  ChromaDB: Tìm thấy {len(formatted)} kết quả cho query: '{query[:60]}'")
        return formatted

    except Exception as e:
        print(f"  ChromaDB: Lỗi khi tìm kiếm: {e}")
        return []


def get_stats() -> Dict:
    """Thống kê ChromaDB."""
    collection = _get_collection()
    total = collection.count()

    # Lấy tất cả metadata để thống kê
    if total > 0:
        all_meta = collection.get(include=["metadatas"])["metadatas"]
        tickers = list(set(m["ticker"] for m in all_meta))
        periods = list(set(m["period"] for m in all_meta))
        sources = list(set(m["source"] for m in all_meta))
    else:
        tickers = periods = sources = []

    return {
        "total_documents": total,
        "tickers": tickers,
        "periods": periods,
        "sources": sources,
        "chroma_dir": CHROMA_DIR
    }


def reset_collection() -> None:
    """Xóa toàn bộ collection (dùng khi cần re-index)."""
    global _client, _collection
    if _client:
        _client.delete_collection(COLLECTION_NAME)
        _collection = None
        print("  ChromaDB: Đã xóa collection.")


if __name__ == "__main__":
    import json
    print("=== Test ChromaDB ===")
    print(json.dumps(get_stats(), ensure_ascii=False, indent=2))