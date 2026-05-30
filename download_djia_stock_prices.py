import yfinance as yf
import pandas as pd
import time
import random
import os
from datetime import datetime, date
from requests.exceptions import HTTPError

def get_djia_constituents():
    """
    Get list of companies in the DJIA index. (Lấy danh sách mã chứng khoán của các công ty thuộc DJIA)
    
    The DJIA (Dow Jones Industrial Average) ticker symbol is ^DJI
    """
    
    djia = yf.Ticker("^DJI")
    
    try:
        
        return djia.constituents
    except:
     
        djia_tickers = [
            "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WBA", "WMT"
        ]
     
        return djia_tickers

def download_stock_prices_with_retry(ticker, start_date, end_date, max_retries=5, initial_delay=2):
    """
    Tải dữ liệu giá cổ phiếu lịch sử cho một mã chứng khoán cụ thể, với cơ chế thử lại khi gặp lỗi.
    
    Args:
        ticker (str): Mã chứng khoán (ví dụ: "AAPL").
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        max_retries (int): Số lần thử lại tối đa (mặc định là 5).
        initial_delay (int): Thời gian chờ ban đầu giữa các lần thử lại (mặc định là 2 giây).
        
    Returns:
        DataFrame: Historical stock price data
    """
    for attempt in range(max_retries):
        try:
            
            if attempt > 0:
                sleep_time = initial_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)  # Exponential backoff with jitter
                print(f"Retry {attempt}/{max_retries-1} for {ticker}. Waiting {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
                
           
            print(f"Downloading {ticker} data (attempt {attempt+1}/{max_retries})...")
            ticker_obj = yf.Ticker(ticker)
            
           
            data = ticker_obj.history(period="2y")  
            
            
            if data.empty:
                print(f"No data returned for {ticker} on attempt {attempt+1}")
                continue
                
            
            filtered_data = data.loc[start_date:end_date] if not data.empty else pd.DataFrame()
            
            if filtered_data.empty:
                print(f"No data available for {ticker} in the specified date range")
                
                try:
                    
                    from datetime import datetime, timedelta
                    
                    
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=30)
                    extended_start = start_dt.strftime("%Y-%m-%d")
                    
                    direct_data = yf.download(
                        ticker,
                        start=extended_start,
                        end=end_date,
                        interval="1d",
                        progress=False
                    )
                    
                    if not direct_data.empty:
                        
                        filtered_direct = direct_data.loc[start_date:end_date] if len(direct_data) > 0 else pd.DataFrame()
                        
                        if not filtered_direct.empty:
                            filtered_direct['Ticker'] = ticker
                            filtered_direct = filtered_direct.reset_index()
                            print(f"Successfully downloaded {ticker} data with extended date method")
                            return filtered_direct
                    
                    
                    print(f"Trying with monthly data for {ticker}...")
                    monthly_data = yf.download(
                        ticker,
                        start=start_date,
                        end=end_date,
                        interval="1mo",  
                        progress=False
                    )
                    
                    if not monthly_data.empty:
                        monthly_data['Ticker'] = ticker
                        monthly_data = monthly_data.reset_index()
                        print(f"Successfully downloaded {ticker} monthly data")
                        return monthly_data
                        
                except Exception as direct_e:
                    print(f"Direct download failed for {ticker}: {direct_e}")
                    
            else:
                
                filtered_data['Ticker'] = ticker
                
                
                filtered_data = filtered_data.reset_index()
                
                print(f"Successfully downloaded {ticker} data with {len(filtered_data)} records")
                return filtered_data
                
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Error downloading {ticker} (attempt {attempt+1}): {e}")
            
            
            if "json" in error_msg or "expecting value" in error_msg:
                time.sleep(5)  
    
    
    print(f"Failed to download data for {ticker} after {max_retries} attempts")
    
    
    empty_df = pd.DataFrame({
        'Date': [],
        'Open': [],
        'High': [], 
        'Low': [],
        'Close': [],
        'Volume': [],
        'Dividends': [],
        'Stock Splits': [],
        'Ticker': []
    })
    
    return empty_df

def main():
    # Define the date range
    start_date = "2022-01-01"
    end_date = date.today().strftime('%Y-%m-%d') 
    
    print(f"Downloading stock prices from {start_date} to {end_date}")
    
    
    output_dir = "stock_prices"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Fetching DJIA constituents...")
    tickers = get_djia_constituents()
    
    if not tickers:
        print("Failed to retrieve DJIA constituents.")
        return
    
    print(f"Found {len(tickers)} companies in the DJIA index.")
    
    
    all_prices = pd.DataFrame()
    
    for i, ticker in enumerate(tickers, 1):
        print(f"Downloading price data for {ticker} ({i}/{len(tickers)})...")
        
        
        prices = download_stock_prices_with_retry(ticker, start_date, end_date)
        
        if not prices.empty:
            
            all_prices = pd.concat([all_prices, prices])
            
           
            ticker_file = os.path.join(output_dir, f"{ticker}_prices.csv")
            prices.to_csv(ticker_file, index=False)
            print(f"  - Saved {ticker} data to {ticker_file}")
        
        
        time.sleep(1.5)
    
    
    if not all_prices.empty:
        
        timestamp = datetime.now().strftime('%Y%m%d')
        combined_file = os.path.join(output_dir, f"djia_prices_{timestamp}.csv")
        
        
        all_prices.to_csv(combined_file, index=False)
        print(f"\nAll stock prices saved to {combined_file}")
        

        print(f"\nSummary:")
        print(f"  - Total companies processed: {len(tickers)}")
        print(f"  - Companies with data: {all_prices['Ticker'].nunique()}")
        print(f"  - Total records: {len(all_prices):,}")
        print(f"  - Date range: {all_prices['Date'].min()} to {all_prices['Date'].max()}")
    else:
        print("No data was downloaded successfully.")

if __name__ == "__main__":
    main() 