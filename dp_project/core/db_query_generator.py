# core/db_query_generator.py
import os
from dotenv import load_dotenv
import json
from sqlalchemy import create_engine, text, exc as sqlalchemy_exc
from google import genai
from google.genai import types
import time
from typing import Dict, Any, List, Optional

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

MODEL_NAME = "gemini-2.5-flash"

if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY not set.")
if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    print("WARNING: Database env vars not fully set.")

gemini_client = None
db_engine = None

if GOOGLE_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
        print(f"--- DB Query Generator: GenAI Client ({MODEL_NAME}) initialized. ---")
    except Exception as e:
        print(f"--- DB Query Generator: Error initializing GenAI Client: {e} ---")

if all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    try:
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        db_engine = create_engine(DATABASE_URL)
        print("--- DB Query Generator: PostgreSQL engine created. ---")
    except Exception as e:
        print(f"--- DB Query Generator: Error creating PostgreSQL engine: {e} ---")

DB_SCHEMA_DESCRIPTION = """
You have access to a PostgreSQL database with the following tables:

Table: companies
  id (PK), ticker (UNIQUE), company_name, sector, industry, exchange, country, summary, website

Table: daily_stock_prices
  id (PK), company_id (FK->companies.id), price_date (DATE),
  open_price, high_price, low_price, close_price (NUMERIC), volume (BIGINT)

Important rules:
- Always SELECT c.ticker for identification.
- Use close_price for "price" or "closing price".
- For latest price: ORDER BY price_date DESC LIMIT 1.
- For multiple tickers: WHERE c.ticker IN ('AAPL', 'MSFT').
- For company info (sector, industry, summary, website): query companies table.
- For RSI, MACD, Bollinger or ANY technical indicator: ALWAYS fetch the last 60 rows of OHLCV data (close_price, high_price, low_price, open_price, volume, price_date) for the ticker. NEVER output NO_QUERY_POSSIBLE for technical indicators.
- If cannot form a query for non-technical questions: output NO_QUERY_POSSIBLE.

Examples:
Latest price:
  SELECT c.ticker, dsp.close_price, dsp.price_date FROM daily_stock_prices dsp JOIN companies c ON dsp.company_id = c.id WHERE c.ticker = 'AAPL' ORDER BY dsp.price_date DESC LIMIT 1;

RSI, MACD, Bollinger or any technical indicator:
  SELECT c.ticker, dsp.close_price, dsp.high_price, dsp.low_price, dsp.open_price, dsp.volume, dsp.price_date FROM daily_stock_prices dsp JOIN companies c ON dsp.company_id = c.id WHERE c.ticker = 'AAPL' ORDER BY dsp.price_date DESC LIMIT 60;

Cumulative return (fetch all price data, let Python calculate):
  SELECT c.ticker, dsp.close_price, dsp.high_price, dsp.low_price, dsp.open_price, dsp.volume, dsp.price_date FROM daily_stock_prices dsp JOIN companies c ON dsp.company_id = c.id WHERE c.ticker = 'AAPL' ORDER BY dsp.price_date ASC;

Company sector:
  SELECT c.ticker, c.sector FROM companies c WHERE c.ticker = 'MSFT';

Compare 2 companies on a date:
  SELECT c.ticker, dsp.close_price, dsp.price_date FROM daily_stock_prices dsp JOIN companies c ON dsp.company_id = c.id WHERE c.ticker IN ('AAPL', 'MSFT') AND dsp.price_date = '2024-10-01';
"""


def generate_sql_query_from_analysis(analyzed_query: Dict[str, Any]) -> Optional[str]:
    if not gemini_client:
        print("  SQL Gen: GenAI Client not initialized.")
        return None

    original_question = analyzed_query.get("original_query", "")
    query_type = analyzed_query.get("query_type", "unknown")
    metrics: Optional[List[str]] = analyzed_query.get("financial_metrics", [])
    report_period = analyzed_query.get("report_period")

    # Normalize ticker về list
    tickers = analyzed_query.get("ticker")
    if isinstance(tickers, str):
        tickers = [tickers]
    elif tickers is None:
        tickers = []

    metrics_str = ", ".join(metrics) if metrics else "Not specified"
    tickers_str = ", ".join(tickers) if tickers else "Not specified"

    prompt = f"""{DB_SCHEMA_DESCRIPTION}

User question: {original_question}
Query type: {query_type}
Ticker(s): {tickers_str}
Metrics requested: {metrics_str}
Period/Date: {report_period or 'N/A'}

Generate a single PostgreSQL SELECT query. Output ONLY the SQL. If impossible, output NO_QUERY_POSSIBLE."""

    try:
        print(f"  SQL Gen: Generating SQL for: '{original_question}'")

        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )

        sql_query = response.text.strip() if response.text else ""

        # Cleanup markdown fences
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip().rstrip(';')

        print(f"  SQL Gen: Generated: {sql_query}")

        if "NO_QUERY_POSSIBLE" in sql_query.upper() or not sql_query:
            return None

        # Chấp nhận cả WITH (CTE) và SELECT
        sql_upper = sql_query.upper().strip()
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            print(f"  SQL Gen: Not a SELECT/WITH statement.")
            return None

        return sql_query

    except Exception as e:
        print(f"  SQL Gen: Error: {e}")
        return None


def execute_sql_query(sql_query: str):
    if not db_engine:
        print("  DB Exec: Engine not initialized.")
        return None
    if not sql_query:
        return None

    print(f"  DB Exec: Executing: {sql_query}")
    try:
        with db_engine.connect() as connection:
            result = connection.execute(text(sql_query))
            rows = result.mappings().all()
            print(f"  DB Exec: {len(rows)} row(s) returned.")
            return [dict(row) for row in rows]
    except sqlalchemy_exc.SQLAlchemyError as e:
        print(f"  DB Exec: SQLAlchemy error: {e}")
        return None
    except Exception as e:
        print(f"  DB Exec: Error: {e}")
        return None


def get_data_from_postgres_for_query(analyzed_query_input: Dict[str, Any]) -> Dict[str, Any]:
    print(f"\n--- DB Query Generator: Processing query ---")

    query_type = analyzed_query_input.get("query_type")

    # Normalize ticker
    tickers = analyzed_query_input.get("ticker")
    if isinstance(tickers, str):
        tickers = [tickers]
        analyzed_query_input = {**analyzed_query_input, "ticker": tickers}

    proceed_with_sql = False
    reason = ""

    if query_type == "number":
        if analyzed_query_input.get("financial_metrics"):
            proceed_with_sql = True
        else:
            reason = "No financial_metrics for 'number' query."
    elif query_type == "general_query":
        if tickers and len(tickers) > 0:
            proceed_with_sql = True
        else:
            reason = "'general_query' needs specific tickers."
    elif query_type == "report":
        if tickers and len(tickers) > 0 and analyzed_query_input.get("financial_metrics"):
            proceed_with_sql = True
        else:
            reason = "'report' needs tickers and metrics."
    else:
        reason = f"Query type '{query_type}' does not need SQL."

    if not proceed_with_sql:
        print(f"  Skipping SQL: {reason}")
        return {"status": "skipped_sql_generation", "reason": reason, "data": None, "sql_query": None}

    sql_query = generate_sql_query_from_analysis(analyzed_query_input)
    if not sql_query:
        return {"status": "sql_generation_failed", "data": None, "sql_query": None}

    query_result = execute_sql_query(sql_query)

    if query_result is None:
        status = "sql_execution_failed"
    elif not query_result:
        status = "sql_execution_success_no_data"
    else:
        status = "success"

    return {
        "status": status,
        "data": query_result if isinstance(query_result, list) else None,
        "sql_query": sql_query
    }


# -------------------------------------------------------
# Tích hợp Technical Indicators + Real-time Fallback
# -------------------------------------------------------
from core.indicators import calculate_indicators as _calc_indicators
from core.realtime_fetcher import check_and_fetch_if_needed, fetch_fundamental_indicators


def get_data_and_indicators(analyzed_query_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrapper: Query DB + Real-time fallback + Technical Indicators.

    Luồng:
    1. Query PostgreSQL
    2. Nếu DB trống/cũ → fetch từ Yahoo Finance → lưu DB → query lại
    3. Nếu cần indicators → tính RSI, MACD, Bollinger...
    """
    # Normalize ticker
    tickers = analyzed_query_input.get("ticker") or []
    if isinstance(tickers, str):
        tickers = [tickers]
    ticker = tickers[0] if tickers else None

    # Bước 1: Query DB
    db_result = get_data_from_postgres_for_query(analyzed_query_input)
    price_data = db_result.get("data") or []

    # Bước 2: Real-time fallback nếu DB không có data
    if ticker and db_result.get("status") in [
        "sql_execution_success_no_data",
        "sql_execution_failed",
        "sql_generation_failed"
    ]:
        print(f"  Fallback: DB không có data cho '{ticker}'. Fetch từ Yahoo Finance...")
        fetch_result = check_and_fetch_if_needed(ticker, price_data)

        if fetch_result and fetch_result.get("status") == "success":
            print(f"  Fallback: Fetch xong, query lại DB...")
            db_result  = get_data_from_postgres_for_query(analyzed_query_input)
            price_data = db_result.get("data") or []
            db_result["realtime_fetch"] = fetch_result
        else:
            db_result["realtime_fetch"] = fetch_result

    # Bước 3: Tính Technical Indicators nếu cần
    metrics = analyzed_query_input.get("financial_metrics") or []
    technical_keywords = [
        "RSI", "MACD", "BOLLINGER", "SMA", "EMA",
        "VWAP", "VOLATILITY", "STOCHASTIC", "STOCH",
        "MOVING AVERAGE", "TECHNICAL", "CUMULATIVE RETURN", "RETURN", "CUMULATIVE"
    ]
    fundamental_keywords = [
        "P/E", "PE RATIO", "EPS", "EARNINGS PER SHARE",
        "DEBT TO EQUITY", "DEBT-TO-EQUITY", "ROE", "RETURN ON EQUITY",
        "DIVIDEND YIELD", "DIVIDEND", "FUNDAMENTAL", "P/E RATIO"
    ]

    needs_indicators = any(
        kw in m.upper()
        for m in metrics
        for kw in technical_keywords
    )
    needs_fundamentals = any(
        kw in m.upper()
        for m in metrics
        for kw in fundamental_keywords
    )

    if needs_indicators:
        if price_data:
            print(f"  Indicators: Tính {metrics} từ {len(price_data)} bản ghi...")
            db_result["indicators"] = _calc_indicators(price_data, metrics)
        else:
            db_result["indicators"] = {"error": "Không có dữ liệu giá để tính chỉ số."}

    #  Fetch Fundamental Indicators từ Yahoo Finance
    if needs_fundamentals and ticker:
        print(f"  Fundamentals: Fetch P/E, EPS, ROE... cho '{ticker}'...")
        db_result["fundamental_indicators"] = fetch_fundamental_indicators(ticker)

    return db_result