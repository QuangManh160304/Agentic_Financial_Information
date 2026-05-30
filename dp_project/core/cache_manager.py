# core/cache_manager.py
import hashlib
import time
import json
import os
from typing import Optional

# Đường dẫn file cache: dp_project/cache/cache_data.json
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "cache_data.json")

# TTL (giây)
CACHE_TTL = {
    "number":           5 * 60,        # Giá cổ phiếu → 5 phút
    "general_query":    24 * 60 * 60,  # Thông tin công ty → 1 ngày
    "report":           24 * 60 * 60,  # Báo cáo → 1 ngày
    "general_greeting": None,          # Chào hỏi → không cache
    "unknown":          None,          # Không rõ → không cache
}

_cache: dict = {}


def _load_cache_from_file() -> None:
    global _cache
    os.makedirs(CACHE_DIR, exist_ok=True)

    if not os.path.exists(CACHE_FILE):
        _cache = {}
        print(f"  Cache: Chưa có file cache, bắt đầu từ rỗng.")
        return

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        print(f"  Cache: Đã load {len(_cache)} entries từ {CACHE_FILE}")
    except Exception as e:
        print(f"  Cache: Lỗi khi đọc file cache ({e}), bắt đầu từ rỗng.")
        _cache = {}


def _save_cache_to_file() -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  Cache: Lỗi khi ghi file cache: {e}")


def _cleanup_expired() -> None:
    now = time.time()
    expired_keys = [k for k, v in _cache.items() if now > v["expired_at"]]
    if expired_keys:
        for k in expired_keys:
            del _cache[k]
        _save_cache_to_file()
        print(f"  Cache: Đã xóa {len(expired_keys)} entry hết hạn.")


def _make_cache_key(user_query: str) -> str:
    normalized = user_query.strip().lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def get_from_cache(user_query: str) -> Optional[str]:
    key = _make_cache_key(user_query)
    entry = _cache.get(key)

    if entry is None:
        print(f"  Cache: MISS — '{user_query[:60]}'")
        return None

    if time.time() > entry["expired_at"]:
        del _cache[key]
        _save_cache_to_file()
        print(f"  Cache: EXPIRED — '{user_query[:60]}'")
        return None

    remaining = int(entry["expired_at"] - time.time())
    print(f"  Cache: HIT ⚡ — '{user_query[:60]}' (còn {remaining}s)")
    return entry["answer"]


def save_to_cache(user_query: str, query_type: str, answer: str) -> None:
    ttl = CACHE_TTL.get(query_type)

    if ttl is None:
        print(f"  Cache: SKIP — query_type '{query_type}' không cần cache.")
        return

    key = _make_cache_key(user_query)
    _cache[key] = {
        "answer":     answer,
        "expired_at": time.time() + ttl,
        "query_type": query_type,
        "query":      user_query[:200],
        "saved_at":   time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    _save_cache_to_file()
    print(f"  Cache: SAVED — type='{query_type}', TTL={ttl}s, query='{user_query[:60]}'")


def clear_cache() -> None:
    global _cache
    _cache = {}
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    print("  Cache: Đã xóa toàn bộ cache.")


def get_cache_stats() -> dict:
    now = time.time()
    active = [e for e in _cache.values() if now <= e["expired_at"]]
    expired_list = [e for e in _cache.values() if now > e["expired_at"]]
    return {
        "cache_file":      CACHE_FILE,
        "total_entries":   len(_cache),
        "active_entries":  len(active),
        "expired_entries": len(expired_list),
        "entries": [
            {
                "query":      e["query"],
                "query_type": e["query_type"],
                "saved_at":   e["saved_at"],
                "expires_in": f"{max(0, int(e['expired_at'] - now))}s",
            }
            for e in _cache.values()
        ]
    }


# Load cache từ file khi import
_load_cache_from_file()
_cleanup_expired()


if __name__ == "__main__":
    print("=== Test Cache Manager ===")
    save_to_cache("What is Apple stock price?", "number", "Apple (AAPL) is $260.48")
    save_to_cache("What sector is Microsoft?", "general_query", "Microsoft is in Technology.")
    save_to_cache("xin chào", "general_greeting", "Xin chào!")  # Không cache

    print(get_from_cache("What is Apple stock price?"))   # HIT
    print(get_from_cache("What sector is Microsoft?"))    # HIT
    print(get_from_cache("xin chào"))                     # MISS
    print(get_from_cache("câu chưa có"))                  # MISS

    print(json.dumps(get_cache_stats(), ensure_ascii=False, indent=2))