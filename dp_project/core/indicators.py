# core/indicators.py
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional


def calculate_indicators(price_data: List[Dict], metrics: List[str]) -> Dict[str, Any]:
    """
    Tính toán các chỉ số kỹ thuật và thống kê từ dữ liệu giá.

    Args:
        price_data: List các dict từ PostgreSQL
                    [{"price_date": ..., "close_price": ..., "high_price": ...,
                      "low_price": ..., "volume": ...}, ...]
        metrics: List các chỉ số cần tính

    Returns:
        Dict kết quả các chỉ số
    """
    if not price_data:
        return {"error": "Không có dữ liệu giá để tính chỉ số."}

    # Chuyển sang DataFrame
    df = pd.DataFrame(price_data)
    if "price_date" in df.columns:
        df["price_date"] = pd.to_datetime(df["price_date"])
        df = df.sort_values("price_date").reset_index(drop=True)

    # Đảm bảo các cột số đúng kiểu
    for col in ["close_price", "high_price", "low_price", "open_price", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    close = df["close_price"] if "close_price" in df.columns else pd.Series([], dtype=float)
    results = {}

    if "price_date" in df.columns and len(df) > 0:
        results["latest_date"] = str(df["price_date"].iloc[-1].date())
    if "close_price" in df.columns and len(df) > 0:
        results["latest_close_price"] = round(float(close.iloc[-1]), 2)
    results["data_points"] = len(df)
    errors = []

    metrics_upper = [m.upper() for m in (metrics or [])]

    # --- RSI ---
    if any(m in metrics_upper for m in ["RSI", "RSI_14"]):
        try:
            results["RSI_14"] = _calculate_rsi(close, period=14)
        except Exception as e:
            errors.append(f"RSI: {e}")

    # --- MACD ---
    if "MACD" in metrics_upper:
        try:
            results["MACD"] = _calculate_macd(close)
        except Exception as e:
            errors.append(f"MACD: {e}")

    # --- Bollinger Bands ---
    if any(m in metrics_upper for m in ["BOLLINGER", "BOLLINGER BANDS", "BB"]):
        try:
            results["Bollinger_Bands"] = _calculate_bollinger(close, period=20)
        except Exception as e:
            errors.append(f"Bollinger: {e}")

    # --- SMA ---
    if any(m in metrics_upper for m in ["SMA", "SIMPLE MOVING AVERAGE", "MOVING AVERAGE"]):
        try:
            results["SMA_20"] = _calculate_sma(close, period=20)
            results["SMA_50"] = _calculate_sma(close, period=50)
        except Exception as e:
            errors.append(f"SMA: {e}")

    # --- EMA ---
    if any(m in metrics_upper for m in ["EMA", "EXPONENTIAL MOVING AVERAGE"]):
        try:
            results["EMA_12"] = _calculate_ema(close, period=12)
            results["EMA_26"] = _calculate_ema(close, period=26)
        except Exception as e:
            errors.append(f"EMA: {e}")

    # --- VWAP ---
    if "VWAP" in metrics_upper:
        try:
            if "volume" in df.columns and "high_price" in df.columns and "low_price" in df.columns:
                results["VWAP"] = _calculate_vwap(df)
            else:
                errors.append("VWAP: Thiếu cột volume/high/low.")
        except Exception as e:
            errors.append(f"VWAP: {e}")

    # --- Volatility ---
    if any(m in metrics_upper for m in ["VOLATILITY", "VOL"]):
        try:
            results["Volatility_30d"] = _calculate_volatility(close, period=30)
        except Exception as e:
            errors.append(f"Volatility: {e}")

    # --- Stochastic Oscillator ---
    if any(m in metrics_upper for m in ["STOCHASTIC", "STOCH"]):
        try:
            if "high_price" in df.columns and "low_price" in df.columns:
                results["Stochastic"] = _calculate_stochastic(df)
            else:
                errors.append("Stochastic: Thiếu cột high/low.")
        except Exception as e:
            errors.append(f"Stochastic: {e}")

    # --- Cumulative Return ---
    if any(m in metrics_upper for m in ["CUMULATIVE RETURN", "CUMULATIVE", "RETURN"]):
        try:
            results["Cumulative_Return"] = _calculate_cumulative_return(close)
        except Exception as e:
            errors.append(f"Cumulative Return: {e}")

    if errors:
        results["errors"] = errors

    return results


# -------------------------------------------------------
# Các hàm tính chỉ số kỹ thuật
# -------------------------------------------------------

def _calculate_rsi(close: pd.Series, period: int = 14) -> Dict:
    """Relative Strength Index."""
    if len(close) < period + 1:
        return {"error": f"Cần ít nhất {period+1} điểm dữ liệu."}

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = round(float(rsi.iloc[-1]), 2)

    if current_rsi >= 70:
        signal = "Overbought (quá mua) — có thể điều chỉnh giảm"
    elif current_rsi <= 30:
        signal = "Oversold (quá bán) — có thể phục hồi tăng"
    else:
        signal = "Neutral (trung tính)"

    return {"value": current_rsi, "signal": signal, "period": period}


def _calculate_macd(close: pd.Series,
                    fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
    """Moving Average Convergence Divergence."""
    if len(close) < slow + signal:
        return {"error": f"Cần ít nhất {slow + signal} điểm dữ liệu."}

    ema_fast    = close.ewm(span=fast,   adjust=False).mean()
    ema_slow    = close.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line

    current_macd      = round(float(macd_line.iloc[-1]),   4)
    current_signal    = round(float(signal_line.iloc[-1]),  4)
    current_histogram = round(float(histogram.iloc[-1]),    4)

    trend = "Bullish (xu hướng tăng)" if current_macd > current_signal else "Bearish (xu hướng giảm)"

    return {
        "macd_line":   current_macd,
        "signal_line": current_signal,
        "histogram":   current_histogram,
        "trend":       trend,
        "params":      f"EMA({fast},{slow},{signal})"
    }


def _calculate_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict:
    """Bollinger Bands."""
    if len(close) < period:
        return {"error": f"Cần ít nhất {period} điểm dữ liệu."}

    sma   = close.rolling(window=period).mean()
    std   = close.rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std

    current_price = round(float(close.iloc[-1]),  2)
    upper_band    = round(float(upper.iloc[-1]),   2)
    middle_band   = round(float(sma.iloc[-1]),     2)
    lower_band    = round(float(lower.iloc[-1]),   2)

    band_width = upper_band - lower_band
    position_pct = round((current_price - lower_band) / band_width * 100, 1) if band_width > 0 else 50.0

    if current_price >= upper_band:
        signal = "Giá chạm dải trên — có thể quá mua"
    elif current_price <= lower_band:
        signal = "Giá chạm dải dưới — có thể quá bán"
    else:
        signal = "Giá trong dải — bình thường"

    return {
        "upper_band":    upper_band,
        "middle_band":   middle_band,
        "lower_band":    lower_band,
        "current_price": current_price,
        "position_pct":  f"{position_pct}% từ dải dưới",
        "signal":        signal,
        "period":        period
    }


def _calculate_sma(close: pd.Series, period: int = 20) -> Dict:
    """Simple Moving Average."""
    if len(close) < period:
        return {"error": f"Cần ít nhất {period} điểm dữ liệu."}

    sma = close.rolling(window=period).mean()
    current_sma   = round(float(sma.iloc[-1]),   2)
    current_price = round(float(close.iloc[-1]),  2)

    trend = "Giá trên SMA — xu hướng tăng" if current_price > current_sma \
            else "Giá dưới SMA — xu hướng giảm"

    return {"value": current_sma, "current_price": current_price, "trend": trend, "period": period}


def _calculate_ema(close: pd.Series, period: int = 12) -> Dict:
    """Exponential Moving Average."""
    if len(close) < period:
        return {"error": f"Cần ít nhất {period} điểm dữ liệu."}

    ema = close.ewm(span=period, adjust=False).mean()
    current_ema   = round(float(ema.iloc[-1]),   2)
    current_price = round(float(close.iloc[-1]),  2)

    trend = "Giá trên EMA — xu hướng tăng" if current_price > current_ema \
            else "Giá dưới EMA — xu hướng giảm"

    return {"value": current_ema, "current_price": current_price, "trend": trend, "period": period}


def _calculate_vwap(df: pd.DataFrame) -> Dict:
    """Volume Weighted Average Price."""
    typical_price = (df["high_price"] + df["low_price"] + df["close_price"]) / 3
    vwap = (typical_price * df["volume"]).sum() / df["volume"].sum()
    current_price = round(float(df["close_price"].iloc[-1]), 2)
    vwap_val      = round(float(vwap), 2)

    signal = "Giá trên VWAP — bullish" if current_price > vwap_val else "Giá dưới VWAP — bearish"

    return {"value": vwap_val, "current_price": current_price, "signal": signal}


def _calculate_volatility(close: pd.Series, period: int = 30) -> Dict:
    """Độ biến động giá (annualized volatility)."""
    if len(close) < period:
        return {"error": f"Cần ít nhất {period} điểm dữ liệu."}

    returns    = close.pct_change().dropna()
    daily_vol  = returns.tail(period).std()
    annual_vol = daily_vol * np.sqrt(252)

    level = "Cao" if annual_vol > 0.3 else ("Trung bình" if annual_vol > 0.15 else "Thấp")

    return {
        "daily_volatility":  round(float(daily_vol)  * 100, 2),
        "annual_volatility": round(float(annual_vol) * 100, 2),
        "level":             level,
        "period":            period
    }


def _calculate_stochastic(df: pd.DataFrame, period: int = 14) -> Dict:
    """Stochastic Oscillator %K và %D."""
    if len(df) < period:
        return {"error": f"Cần ít nhất {period} điểm dữ liệu."}

    low_min  = df["low_price"].rolling(window=period).min()
    high_max = df["high_price"].rolling(window=period).max()

    k = 100 * (df["close_price"] - low_min) / (high_max - low_min)
    d = k.rolling(window=3).mean()

    k_val = round(float(k.iloc[-1]), 2)
    d_val = round(float(d.iloc[-1]), 2)

    if k_val >= 80:
        signal = "Overbought (quá mua)"
    elif k_val <= 20:
        signal = "Oversold (quá bán)"
    else:
        signal = "Neutral"

    return {"K": k_val, "D": d_val, "signal": signal, "period": period}


def _calculate_cumulative_return(close: pd.Series) -> Dict:
    """Cumulative Return — Lợi nhuận tích lũy. MỚI"""
    if len(close) < 2:
        return {"error": "Cần ít nhất 2 điểm dữ liệu."}

    start_price = round(float(close.iloc[0]),  2)
    end_price   = round(float(close.iloc[-1]), 2)
    cumulative_return = round((end_price / start_price - 1) * 100, 2)

    if cumulative_return > 0:
        signal = f"Tăng {cumulative_return}% trong kỳ"
    elif cumulative_return < 0:
        signal = f"Giảm {abs(cumulative_return)}% trong kỳ"
    else:
        signal = "Không thay đổi"

    return {
        "start_price":       start_price,
        "end_price":         end_price,
        "cumulative_return": f"{cumulative_return}%",
        "signal":            signal,
        "data_points":       len(close)
    }


if __name__ == "__main__":
    import json, random
    random.seed(42)

    base_price = 200.0
    test_data = []
    for i in range(60):
        base_price += random.uniform(-3, 3)
        test_data.append({
            "price_date":  f"2025-0{(i//30)+1}-{(i%30)+1:02d}",
            "close_price": round(base_price, 2),
            "high_price":  round(base_price + random.uniform(0, 2), 2),
            "low_price":   round(base_price - random.uniform(0, 2), 2),
            "open_price":  round(base_price + random.uniform(-1, 1), 2),
            "volume":      random.randint(10000000, 50000000),
        })

    metrics = ["RSI", "MACD", "Bollinger", "SMA", "EMA", "VWAP",
               "Volatility", "Stochastic", "Cumulative Return"]
    results = calculate_indicators(test_data, metrics)
    print("=== Test Technical Indicators ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))