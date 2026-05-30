# financial_chatbot_app.py
import gradio as gr
from agent.langgraph_orchestrator import create_answer_to_gradio


def process_user_query(message: str, history: list) -> str:
    return create_answer_to_gradio(message, history)


def main():
    print("--- Khởi chạy Giao diện Chatbot Tài chính Gradio ---")

    iface = gr.ChatInterface(
        fn=process_user_query,
        title="Hệ thống Thông tin Tài chính Thông minh (Agentic Financial Information System)",
        description="Chào mừng bạn! Hãy nhập câu hỏi và hệ thống sẽ trả lời.",
        chatbot=gr.Chatbot(height=600),
        textbox=gr.Textbox(
            placeholder="Nhập câu hỏi của bạn ở đây...",
            container=False,
            scale=7
        ),
        examples=[
            ["What is Apple's stock price today?"],
            ["Show me Apple's Q1 2025 revenue"],
            ["What is Apple's net income in Q2 2025?"],
            ["What sector is Microsoft in?"],
            ["Compare Apple and Microsoft stock price"],
            ["xin chào"],
        ],
    )

    iface.launch(
        server_name="0.0.0.0",
        server_port=7860,
    )
    print("--- Giao diện Gradio đã đóng ---")


if __name__ == "__main__":
    main()