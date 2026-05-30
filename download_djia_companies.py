import yfinance as yf
import pandas as pd
import time
import random
import csv
from datetime import datetime
from requests.exceptions import HTTPError

def get_djia_constituents():
    """
    Get list of companies in the DJIA index.
    
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

def get_company_info_with_retry(ticker, max_retries=5, initial_delay=2):
    """
    Get detailed information about a company using its ticker symbol.
    Implements retry logic with exponential backoff to handle rate limits.
    """
    retry_count = 0
    delay = initial_delay
    
    while retry_count < max_retries:
        try:
            company = yf.Ticker(ticker)
            
            
            time.sleep(delay)
            
            # Basic info
            info = company.info
            
            
            relevant_info = {
                "symbol": ticker,
                "name": info.get("shortName", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "country": info.get("country", ""),
                "website": info.get("website", ""),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "dividend_yield": info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0,
                "52_week_high": info.get("fiftyTwoWeekHigh", 0),
                "52_week_low": info.get("fiftyTwoWeekLow", 0),
                "description": info.get("longBusinessSummary", "")
            }
            
            return relevant_info
            
        except HTTPError as e:
            if "429" in str(e):  
                retry_count += 1
                if retry_count < max_retries:
                    
                    jitter = random.uniform(0, 1.0)
                    wait_time = delay + jitter
                    print(f"Rate limited. Waiting {wait_time:.2f} seconds before retry {retry_count}/{max_retries} for {ticker}...")
                    time.sleep(wait_time)
                    # Exponential backoff
                    delay *= 2
                else:
                    print(f"Max retries reached for {ticker}. Skipping.")
                    raise
            else:
                
                raise
        except Exception as e:
            
            raise

def main():
    print("Fetching DJIA constituents...")
    tickers = get_djia_constituents()
    
    if not tickers:
        print("Failed to retrieve DJIA constituents.")
        return
    
    print(f"Found {len(tickers)} companies in the DJIA index.")
    
    
    companies_info = []
    
    for i, ticker in enumerate(tickers, 1):
        print(f"Downloading information for {ticker} ({i}/{len(tickers)})...")
        try:
            
            company_info = get_company_info_with_retry(ticker)
            companies_info.append(company_info)
            
            time.sleep(2)
        except Exception as e:
            print(f"Error getting information for {ticker}: {e}")
    
    
    print("Saving company information to CSV...")
    df = pd.DataFrame(companies_info)
    csv_filename = f"djia_companies_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(csv_filename, index=False, quoting=csv.QUOTE_NONNUMERIC)
    print(f"Data saved to {csv_filename}")

if __name__ == "__main__":
    main() 
