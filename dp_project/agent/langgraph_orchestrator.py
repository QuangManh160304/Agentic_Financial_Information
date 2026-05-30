# agent/langgraph_orchestrator.py
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from core.llm_handler import analyze_query_native_sdk
from core.db_query_generator import get_data_and_indicators
from core.response_synthesizer import generate_final_response
from core.cache_manager import get_from_cache, save_to_cache
from rag.rag_handler import search_reports  # RAG


# --- 1. State ---
class AgentState(TypedDict):
    original_user_query: str
    chat_history: List[List[str]]
    analyzed_query: Optional[Dict[str, Any]]
    db_query_results: Optional[Dict[str, Any]]
    rag_results: Optional[Dict[str, Any]]          
    final_answer: Optional[str]
    error_message: Optional[str]


# --- 2. Node Functions ---
def entry_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Entry Node ---")
    return {}

def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Analyzing Query Node ---")
    user_query = state["original_user_query"]
    analysis = analyze_query_native_sdk(user_query)
    if analysis.get("error"):
        return {"error_message": f"Query analysis failed: {analysis.get('error')}"}
    return {"analyzed_query": analysis}

def db_query_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Database Query Node ---")
    analyzed_query = state.get("analyzed_query")
    if not analyzed_query:
        return {"error_message": "Cannot query DB: Analyzed query is missing."}
    db_results = get_data_and_indicators(analyzed_query)
    return {"db_query_results": db_results}

def rag_query_node(state: AgentState) -> Dict[str, Any]:
    """Node mới: Tìm kiếm trong PDF báo cáo tài chính."""
    print("--- LangGraph: RAG Query Node ---")
    analyzed_query = state.get("analyzed_query")
    if not analyzed_query:
        return {"error_message": "Cannot query RAG: Analyzed query is missing."}

    user_query = state["original_user_query"]

    # Lấy ticker và period từ analyzed_query
    tickers = analyzed_query.get("ticker") or []
    ticker = tickers[0] if tickers else None
    period = analyzed_query.get("report_period")

    rag_results = search_reports(
        query=user_query,
        ticker=ticker,
        period=period,
        n_results=5
    )
    return {"rag_results": rag_results}

def synthesize_response_node(state: AgentState) -> Dict[str, Any]:
    print("--- LangGraph: Synthesize Response Node ---")
    user_query = state["original_user_query"]
    chat_history = state["chat_history"]

    context_data = {
        "analyzed_query_details": state.get("analyzed_query"),
        "database_info":          state.get("db_query_results"),
        "report_context":         state.get("rag_results"),  # Thêm RAG context
    }

    if state.get("error_message"):
        context_data["previous_errors"] = state["error_message"]

    response_output = generate_final_response(user_query, context_data, chat_history)
    return {"final_answer": response_output}


# --- 3. Routing ---
def router_after_analysis(state: AgentState) -> str:
    print("--- LangGraph: Router After Analysis ---")

    if state.get("error_message"):
        return "synthesize_direct"

    analyzed_query = state.get("analyzed_query")
    query_type = analyzed_query.get("query_type") if analyzed_query else "unknown"
    print(f"  Query type: {query_type}")

    if query_type == "number":
        return "db_path"
    elif query_type == "general_query":
        return "db_path"
    elif query_type == "report":
        return "rag_path"       #Route mới cho RAG
    else:
        return "synthesize_direct"


# --- 4. Build Graph ---
def create_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("entry",              entry_node)
    workflow.add_node("analyze_query",      analyze_query_node)
    workflow.add_node("query_database",     db_query_node)
    workflow.add_node("query_rag",          rag_query_node)     #Node mới
    workflow.add_node("synthesize_response", synthesize_response_node)

    workflow.set_entry_point("entry")
    workflow.add_edge("entry", "analyze_query")

    workflow.add_conditional_edges(
        "analyze_query",
        router_after_analysis,
        {
            "db_path":         "query_database",
            "rag_path":        "query_rag",          #Edge mới
            "synthesize_direct": "synthesize_response"
        }
    )

    workflow.add_edge("query_database", "synthesize_response")
    workflow.add_edge("query_rag",      "synthesize_response")  #Edge mới
    workflow.add_edge("synthesize_response", END)

    app = workflow.compile()
    print("--- LangGraph: Agent graph compiled successfully! ---")
    return app


# Compile 1 lần khi khởi động
_agent_app = create_agent_graph()


def create_answer_to_gradio(text: str, chat_history: list = []) -> str:
    print(f"\n========== NEW REQUEST: '{text}' ==========")

    # BƯỚC 1: Kiểm tra cache
    cached_answer = get_from_cache(text)
    if cached_answer is not None:
        print(f"  ⚡ Cache HIT — trả về ngay!")
        return cached_answer

    # BƯỚC 2: Chạy LangGraph
    print(f"  Cache MISS — chạy LangGraph...")
    initial_state = AgentState(
        original_user_query=text,
        chat_history=chat_history,
        analyzed_query=None,
        db_query_results=None,
        rag_results=None,
        final_answer=None,
        error_message=None
    )

    final_state = _agent_app.invoke(initial_state)
    answer = final_state["final_answer"]

    # BƯỚC 3: Lưu cache
    analyzed = final_state.get("analyzed_query") or {}
    query_type = analyzed.get("query_type", "unknown")
    save_to_cache(text, query_type, answer)

    return answer


if __name__ == '__main__':
    # Test RAG
    print("=== Test RAG route ===")
    r = create_answer_to_gradio("Show me Apple's Q1 2025 revenue report")
    print(f"Answer: {r[:200]}")