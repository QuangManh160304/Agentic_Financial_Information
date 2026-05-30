# Dockerfile
FROM python:3.12-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài các dependency hệ thống cần thiết
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements trước để tận dụng Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code
COPY . .

# Tạo thư mục cần thiết
RUN mkdir -p cache data/chroma_db pdf

# Expose port Gradio
EXPOSE 7860

# Chạy app
CMD ["python", "-u", "financial_chatbot_app.py"]