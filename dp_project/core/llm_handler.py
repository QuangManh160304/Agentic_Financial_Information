# core/llm_handler.py
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_client = None
MODEL_NAME = "gemini-2.5-flash"

if GOOGLE_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
        print(f"--- LLM Handler: Google GenAI Client initialized ({MODEL_NAME}). ---")
    except Exception as e:
        print(f"--- LLM Handler: Error initializing GenAI Client: {e} ---")
else:
    print("--- LLM Handler: Error! GOOGLE_API_KEY not found. ---")

SYSTEM_PROMPT = """You are a highly capable financial query analyzer.
Your ONLY task is to analyze the user's CURRENT query and respond with a single, valid JSON object.
This JSON object MUST contain the following keys: "original_query", "query_type", "company_name", "ticker", "report_period", and "financial_metrics".

Field Definitions:
1. "original_query": (String) EXACT copy of the user's query.
2. "query_type": (String) One of: "number", "report", "general_query", "general_greeting", "unknown".
   - "number": questions about stock prices, financial ratios, market cap, volume, comparisons.
   - "report": questions about financial reports (10-K, 10-Q) for a specific period.
   - "general_query": general questions about a company, products, news.
   - "general_greeting": greetings, thank you, non-informational phrases.
   - "unknown": ambiguous or unrelated queries.
3. "company_name": (List of Strings or null) e.g. ["Apple Inc.", "Microsoft Corporation"]. Null if not found.
4. "ticker": (List of Strings or null) e.g. ["AAPL", "MSFT"]. Null if not found.
5. "report_period": (String or null) e.g. "Q1 2025", "2023 Annual". Null if not applicable.
6. "financial_metrics": (List of Strings or null) e.g. ["stock price", "P/E ratio", "RSI"]. Null if none.

Examples:
Query: "What is Apple's stock price today?"
Response: {"original_query": "What is Apple's stock price today?", "query_type": "number", "company_name": ["Apple Inc."], "ticker": ["AAPL"], "report_period": null, "financial_metrics": ["stock price"]}

Query: "Compare Apple and Microsoft closing price on Jan 15 2025"
Response: {"original_query": "Compare Apple and Microsoft closing price on Jan 15 2025", "query_type": "number", "company_name": ["Apple Inc.", "Microsoft Corporation"], "ticker": ["AAPL", "MSFT"], "report_period": "January 15, 2025", "financial_metrics": ["closing price"]}

Query: "What sector is Microsoft in?"
Response: {"original_query": "What sector is Microsoft in?", "query_type": "general_query", "company_name": ["Microsoft Corporation"], "ticker": ["MSFT"], "report_period": null, "financial_metrics": ["sector"]}

Query: "xin chào"
Response: {"original_query": "xin chào", "query_type": "general_greeting", "company_name": null, "ticker": null, "report_period": null, "financial_metrics": null}

Your entire response MUST be ONLY the JSON object. The user's CURRENT query is: """


def analyze_query_native_sdk(user_query: str) -> dict:
    default_error = {
        "original_query": user_query,
        "query_type": "unknown",
        "company_name": None,
        "ticker": None,
        "report_period": None,
        "financial_metrics": None,
        "error": "Failed to get a valid response from LLM."
    }

    if not gemini_client:
        default_error["error"] = "GenAI Client not initialized."
        return default_error

    full_prompt = f"{SYSTEM_PROMPT}\n\"{user_query}\""

    try:
        print(f"  LLM Handler: Sending prompt for query: '{user_query}'")

        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            )
        )

        llm_output = response.text.strip() if response.text else ""
        print(f"  LLM Handler: Raw output: '{llm_output}'")

        try:
            analysis_dict = json.loads(llm_output)

            # Normalize ticker về list
            ticker_val = analysis_dict.get("ticker")
            if isinstance(ticker_val, str):
                analysis_dict["ticker"] = [ticker_val]

            # Normalize company_name về list
            company_val = analysis_dict.get("company_name")
            if isinstance(company_val, str):
                analysis_dict["company_name"] = [company_val]

            analysis_dict.setdefault("company_name", None)
            analysis_dict.setdefault("ticker", None)
            analysis_dict.setdefault("report_period", None)
            analysis_dict.setdefault("financial_metrics", None)

            if analysis_dict.get("financial_metrics") is None:
                analysis_dict["financial_metrics"] = []

            if analysis_dict.get("original_query") != user_query:
                analysis_dict["original_query"] = user_query

            valid_types = ["number", "report", "general_query", "general_greeting", "unknown"]
            if analysis_dict.get("query_type") not in valid_types:
                analysis_dict["query_type"] = "unknown"

            print(f"  LLM Handler: Parsed: {json.dumps(analysis_dict, ensure_ascii=False)}")
            return analysis_dict

        except json.JSONDecodeError as e:
            default_error["error"] = f"JSON decode error: {e}. Raw: {llm_output}"
            return default_error

    except Exception as e:
        import traceback
        traceback.print_exc()
        default_error["error"] = f"LLM call error: {str(e)}"
        return default_error


if __name__ == "__main__":
    queries = [
        "What is Apple's stock price today?",
        "Compare Apple and Microsoft",
        "xin chào",
        "MSFT P/E ratio?"
    ]
    for q in queries:
        print(f"\nQuery: {q}")
        result = analyze_query_native_sdk(q)
        print(json.dumps(result, indent=2, ensure_ascii=False))