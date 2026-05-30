# 🤖 Agentic Financial Information System

Hệ thống chatbot tài chính thông minh sử dụng LangGraph, cho phép người dùng truy vấn và phân tích thông tin chứng khoán từ nhiều nguồn dữ liệu khác nhau.
---

## 📋 Mục lục

- [Tính năng](#tính-năng)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cài đặt và chạy](#cài-đặt-và-chạy)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Ví dụ câu hỏi](#ví-dụ-câu-hỏi)

---

## ✨ Tính năng

| Tính năng | Mô tả |
|---|---|
| **DB Query** | Truy vấn giá cổ phiếu, thông tin công ty từ PostgreSQL |
| **RAG Module** | Tìm kiếm thông tin từ báo cáo tài chính PDF (ChromaDB) |
| **Technical Indicators** | Tính toán RSI, MACD, Bollinger Bands, SMA, EMA, VWAP, Volatility, Stochastic |
| **Real-time Fallback** | Tự động fetch dữ liệu từ Yahoo Finance khi DB không có |
| **Cache Manager** | Lưu cache vào file JSON, tắt máy vẫn còn |
| **Chat History** | Nhớ ngữ cảnh hội thoại |
| **Smart Routing** | Phân loại câu hỏi và điều hướng đúng luồng xử lý |
| **Docker Deployment** | Triển khai đầy đủ với Docker Compose |

---

## 🏗️ Kiến trúc hệ thống

```
User (Gradio UI)
      ↓
LangGraph Orchestrator
      ├── LLM Handler (phân tích câu hỏi)
      ├── Router (phân loại: number/report/greeting/unknown)
      │     ├── DB Path → DB Query Generator → PostgreSQL
      │     │                └── Real-time Fallback (Yahoo Finance)
      │     │                └── Technical Indicators (RSI, MACD...)
      │     ├── RAG Path → RAG Handler → ChromaDB (PDF)
      │     └── Direct → Response Synthesizer
      └── Response Synthesizer (sinh câu trả lời)
```

---

## 🛠️ Công nghệ sử dụng

| Vai trò | Công nghệ |
|---|---|
| AI Workflow | LangGraph + LangChain |
| LLM | Google Gemini (google-genai) |
| Dữ liệu cấu trúc | PostgreSQL + yfinance |
| Dữ liệu phi cấu trúc | ChromaDB + pdfplumber |
| Phân tích kỹ thuật | pandas + numpy |
| Frontend | Gradio |
| Deployment | Docker + Docker Compose |

---

## 🚀 Cài đặt và chạy

### Yêu cầu
- Docker Desktop đã cài đặt
- Google Gemini API key (lấy tại [aistudio.google.com](https://aistudio.google.com))

### Bước 1 — Clone project

```bash
git clone https://github.com/HaTuMy/Agentic-Financial-Information-.git
cd Agentic-Financial-Information-/dp_project
```

### Bước 2 — Cấu hình môi trường

Tạo file `.env` trong thư mục `dp_project/`:

```env
GOOGLE_API_KEY=your_gemini_api_key_here

DB_HOST=postgres
DB_PORT=5432
DB_NAME=financial_data_db
DB_USER=postgres
DB_PASSWORD=your_password_here
```

### Bước 3 — Đặt PDF báo cáo tài chính (tùy chọn)

Copy các file PDF báo cáo tài chính vào thư mục `pdf/`:
```
dp_project/
└── pdf/
    ├── 10Q-Q1-2025-as-filed.pdf
    └── 10Q-Q2-2025-as-filed.pdf
```

### Bước 4 — Chạy Docker

```bash
docker-compose up --build
```

Lần đầu sẽ mất 3-5 phút để build. Các lần sau chỉ cần:

```bash
docker-compose up
```

### Bước 5 — Import dữ liệu

Mở terminal mới, copy CSV và import vào DB:

```bash
docker cp /path/to/djia_companies_20260411.csv financial_chatbot:/app/djia_companies_20260411.csv
docker cp /path/to/djia_prices_20260411.csv financial_chatbot:/app/djia_prices_20260411.csv
docker exec financial_chatbot python data_ingestion/data_ingestion.py
```

### Bước 6 — Truy cập ứng dụng

Mở trình duyệt vào: **http://localhost:7860**

---

## 📁 Cấu trúc thư mục

```
dp_project/
├── agent/
│   └── langgraph_orchestrator.py   # Điều phối LangGraph
├── core/
│   ├── llm_handler.py              # Phân tích câu hỏi bằng Gemini
│   ├── db_query_generator.py       # Sinh SQL và query PostgreSQL
│   ├── response_synthesizer.py     # Sinh câu trả lời tự nhiên
│   ├── cache_manager.py            # Quản lý cache JSON
│   ├── indicators.py               # Tính toán chỉ số kỹ thuật
│   └── realtime_fetcher.py         # Fetch dữ liệu Yahoo Finance
├── rag/
│   ├── pdf_extractor.py            # Trích xuất text từ PDF
│   ├── chroma_store.py             # Lưu và tìm kiếm ChromaDB
│   └── rag_handler.py              # Xử lý câu hỏi về báo cáo
├── data_ingestion/
│   └── data_ingestion.py           # Import CSV vào PostgreSQL
├── pdf/                            # Thư mục chứa PDF báo cáo
├── cache/                          # Cache tự động tạo
├── financial_chatbot_app.py        # Entry point (Gradio)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

---

## 💬 Ví dụ câu hỏi

### Giá cổ phiếu
```
What is Apple's stock price today?
Compare Goldman Sachs and JPMorgan stock price
```

### Chỉ số kỹ thuật
```
What is Apple's RSI?
What is Apple's MACD?
What is Microsoft's Bollinger Bands?
```

### Báo cáo tài chính (RAG)
```
What does Apple's Q1 2025 financial report say about revenue?
What does Apple's Q2 2025 financial report say about net income?
```

### Thông tin công ty
```
What sector is Microsoft in?
Tell me about Apple's business
```

### Real-time (công ty ngoài DJIA)
```
What is Tesla stock price today?
```

---

## 🐳 Quản lý Docker

```bash
# Khởi động
docker-compose up

# Dừng (giữ data)
docker-compose stop

# Xóa hoàn toàn (mất data)
docker-compose down

# Xem logs
docker logs -f financial_chatbot
```

---

## ⚠️ Lưu ý

- Sử dụng `docker-compose stop` thay vì `docker-compose down` để giữ data trong PostgreSQL
- Quota Gemini Free Tier: 20 requests/ngày cho `gemini-2.5-flash`
- Cache tự động lưu vào `cache/cache_data.json`, reset khi `docker-compose down`
- PDF báo cáo sẽ được index tự động vào ChromaDB lần đầu hỏi về báo cáo
