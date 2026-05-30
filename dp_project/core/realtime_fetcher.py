# core/realtime_fetcher.py
import os
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from typing import Optional, List, Dict
from datetime import datetime, timedelta

load_dotenv()

DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME")
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

_engine = None

def _get_engine():
    global _engine
    if _engine is None and all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        _engine = create_engine(DATABASE_URL)
    return _engine


def fetch_and_save_ticker(ticker: str, days: int = 365) -> Dict:
    """
    Fetch dữ liệu giá từ Yahoo Finance và lưu vào PostgreSQL.

    Args:
        ticker: Mã cổ phiếu (e.g. "AAPL")
        days:   Số ngày lịch sử cần lấy (mặc định 365 ngày)

    Returns:
        Dict với status và số records đã lưu
    """
    print(f"  Realtime Fetcher: Fetching '{ticker}' từ Yahoo Finance ({days} ngày)...")

    engine = _get_engine()
    if not engine:
        return {"status": "error", "message": "DB engine không khởi tạo được."}

    try:
        end_date   = datetime.today()
        start_date = end_date - timedelta(days=days)

        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(start=start_date.strftime("%Y-%m-%d"),
                                end=end_date.strftime("%Y-%m-%d"))

        if df.empty:
            return {"status": "error", "message": f"Không tìm thấy dữ liệu cho '{ticker}'."}

        df = df.reset_index()
        df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.date
        df = df.rename(columns={
            "Date":   "price_date",
            "Open":   "open_price",
            "High":   "high_price",
            "Low":    "low_price",
            "Close":  "close_price",
            "Volume": "volume"
        })

        print(f"  Realtime Fetcher: Tải được {len(df)} bản ghi cho '{ticker}'.")

        saved = _save_to_db(ticker, df, engine)

        return {
            "status":          "success",
            "ticker":          ticker,
            "records_fetched": len(df),
            "records_saved":   saved,
            "date_range":      f"{df['price_date'].min()} → {df['price_date'].max()}"
        }

    except Exception as e:
        print(f"  Realtime Fetcher: Lỗi khi fetch '{ticker}': {e}")
        return {"status": "error", "message": str(e)}


def fetch_fundamental_indicators(ticker: str) -> Dict:
    """
    — Fetch Fundamental Indicators từ Yahoo Finance.
    Bao gồm: P/E Ratio, EPS, Debt-to-Equity, ROE, Dividend Yield.

    Args:
        ticker: Mã cổ phiếu (e.g. "AAPL")

    Returns:
        Dict chứa các chỉ số cơ bản
    """
    print(f"  Realtime Fetcher: Fetching Fundamental Indicators cho '{ticker}'...")

    try:
        info = yf.Ticker(ticker).info

        pe_ratio       = info.get("trailingPE")
        eps            = info.get("trailingEps")
        debt_to_equity = info.get("debtToEquity")
        roe            = info.get("returnOnEquity")
        dividend_yield = info.get("dividendYield")
        market_cap     = info.get("marketCap")
        revenue        = info.get("totalRevenue")
        net_income     = info.get("netIncomeToCommon")

        def fmt_pct(val):
            return f"{round(val * 100, 2)}%" if val is not None else "N/A"

        def fmt_num(val, decimals=2):
            return round(val, decimals) if val is not None else "N/A"

        def fmt_billion(val):
            if val is None:
                return "N/A"
            return f"${round(val / 1e9, 2)}B"

        result = {
            "ticker": ticker,
            "P/E_Ratio": {
                "value":  fmt_num(pe_ratio),
                "signal": _pe_signal(pe_ratio)
            },
            "EPS": {
                "value":  fmt_num(eps),
                "unit":   "USD/share",
                "signal": "Tốt" if eps and eps > 0 else "Âm — công ty đang lỗ"
            },
            "Debt_to_Equity": {
                "value":  fmt_num(debt_to_equity),
                "signal": _de_signal(debt_to_equity)
            },
            "ROE": {
                "value":  fmt_pct(roe),
                "signal": _roe_signal(roe)
            },
            "Dividend_Yield": {
                "value":  fmt_pct(dividend_yield),
                "signal": "Hấp dẫn cho nhà đầu tư thu nhập" if dividend_yield and dividend_yield > 0.02
                          else "Thấp hoặc không có cổ tức"
            },
            "Market_Cap":  fmt_billion(market_cap),
            "Revenue":     fmt_billion(revenue),
            "Net_Income":  fmt_billion(net_income),
        }

        print(f"  Realtime Fetcher: Fundamental Indicators cho '{ticker}' đã lấy xong.")
        return result

    except Exception as e:
        print(f"  Realtime Fetcher: Lỗi khi fetch Fundamental Indicators '{ticker}': {e}")
        return {"error": str(e)}


def _pe_signal(pe: Optional[float]) -> str:
    if pe is None:
        return "N/A"
    if pe > 30:
        return "Cao — có thể định giá quá cao hoặc tiềm năng tăng trưởng lớn"
    elif pe < 10:
        return "Thấp — có thể định giá thấp hoặc công ty gặp khó khăn"
    else:
        return "Trung bình — định giá hợp lý"


def _de_signal(de: Optional[float]) -> str:
    if de is None:
        return "N/A"
    if de > 2:
        return "Cao — công ty phụ thuộc nhiều vào nợ, rủi ro tài chính cao"
    elif de < 0.5:
        return "Thấp — cấu trúc tài chính an toàn"
    else:
        return "Trung bình"


def _roe_signal(roe: Optional[float]) -> str:
    if roe is None:
        return "N/A"
    if roe > 0.15:
        return "Cao — công ty sử dụng vốn hiệu quả"
    elif roe < 0:
        return "Âm — công ty đang thua lỗ"
    else:
        return "Trung bình"


def _save_to_db(ticker: str, df: pd.DataFrame, engine) -> int:
    """Lưu DataFrame giá vào PostgreSQL, tự thêm công ty nếu chưa có."""
    saved_count = 0

    with engine.connect() as conn:
        company_id = _get_or_create_company(ticker, conn)
        if not company_id:
            return 0

        for _, row in df.iterrows():
            try:
                conn.execute(text("""
                    INSERT INTO daily_stock_prices
                        (company_id, price_date, open_price, high_price,
                         low_price, close_price, volume)
                    VALUES
                        (:company_id, :price_date, :open_price, :high_price,
                         :low_price, :close_price, :volume)
                    ON CONFLICT (company_id, price_date) DO NOTHING
                """), {
                    "company_id":  company_id,
                    "price_date":  row["price_date"],
                    "open_price":  float(row["open_price"])  if pd.notna(row["open_price"])  else None,
                    "high_price":  float(row["high_price"])  if pd.notna(row["high_price"])  else None,
                    "low_price":   float(row["low_price"])   if pd.notna(row["low_price"])   else None,
                    "close_price": float(row["close_price"]) if pd.notna(row["close_price"]) else None,
                    "volume":      int(row["volume"])         if pd.notna(row["volume"])       else None,
                })
                saved_count += 1
            except Exception:
                pass

        conn.commit()

    print(f"  Realtime Fetcher: Đã lưu {saved_count} bản ghi cho '{ticker}' vào DB.")
    return saved_count


def _get_or_create_company(ticker: str, conn) -> Optional[int]:
    """Lấy company_id từ DB. Nếu chưa có thì tạo mới."""
    result = conn.execute(
        text("SELECT id FROM companies WHERE ticker = :ticker"),
        {"ticker": ticker}
    ).fetchone()

    if result:
        return result[0]

    print(f"  Realtime Fetcher: Tạo mới công ty '{ticker}' trong DB...")
    try:
        info = yf.Ticker(ticker).info
        conn.execute(text("""
            INSERT INTO companies (ticker, company_name, sector, industry, country, website)
            VALUES (:ticker, :name, :sector, :industry, :country, :website)
            ON CONFLICT (ticker) DO NOTHING
        """), {
            "ticker":   ticker,
            "name":     info.get("shortName", ticker),
            "sector":   info.get("sector", ""),
            "industry": info.get("industry", ""),
            "country":  info.get("country", ""),
            "website":  info.get("website", ""),
        })
        conn.commit()

        result = conn.execute(
            text("SELECT id FROM companies WHERE ticker = :ticker"),
            {"ticker": ticker}
        ).fetchone()
        return result[0] if result else None

    except Exception as e:
        print(f"  Realtime Fetcher: Lỗi khi tạo công ty '{ticker}': {e}")
        return None


def check_and_fetch_if_needed(ticker: str, db_data: List[Dict]) -> Optional[Dict]:
    """
    Kiểm tra dữ liệu DB có đủ không.
    Nếu thiếu → tự động fetch từ Yahoo Finance.
    """
    if db_data and len(db_data) > 0:
        latest_dates = [row.get("price_date") for row in db_data if row.get("price_date")]
        if latest_dates:
            latest = max(latest_dates)
            if hasattr(latest, 'date'):
                latest = latest.date()
            days_old = (datetime.today().date() - latest).days
            if days_old <= 7:
                print(f"  Realtime Fetcher: DB có dữ liệu mới ({days_old} ngày trước). Không cần fetch.")
                return None

        print(f"  Realtime Fetcher: DB có dữ liệu nhưng đã cũ. Fetch thêm data mới...")
    else:
        print(f"  Realtime Fetcher: DB không có dữ liệu cho '{ticker}'. Fetch từ Yahoo Finance...")

    return fetch_and_save_ticker(ticker, days=365)


if __name__ == "__main__":
    import json

    result = fetch_and_save_ticker("AAPL", days=30)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    fundamentals = fetch_fundamental_indicators("AAPL")
    print(json.dumps(fundamentals, ensure_ascii=False, indent=2, default=str))