# core/response_synthesizer.py
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
from typing import Dict, Any, List

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_client = None
MODEL_NAME = "gemini-2.5-flash"

if GOOGLE_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
        print(f"--- Response Synthesizer: GenAI Client ({MODEL_NAME}) initialized. ---")
    except Exception as e:
        print(f"--- Response Synthesizer: Error initializing GenAI Client: {e} ---")
else:
    print("--- Response Synthesizer: GOOGLE_API_KEY not found. ---")


def generate_final_response(
    original_user_query: str,
    context_data: Dict[str, Any],
    chat_history_gradio: List
) -> str:
    if not gemini_client:
        return "Sorry, I cannot process your request — language model not initialized."

    context_json = json.dumps(context_data, indent=2, ensure_ascii=False, default=str)

    #Xử lý cả 2 format history của Gradio
    history_text = ""
    if chat_history_gradio:
        history_text = "\n\nPrevious conversation:\n"
        for turn in chat_history_gradio:
            if isinstance(turn, dict):
                # Format mới: {"role": "user", "content": "..."}
                role = turn.get("role", "")
                content = turn.get("content", "")
                if role == "user":
                    history_text += f"User: {content}\n"
                elif role == "assistant":
                    history_text += f"Assistant: {content}\n"
            elif isinstance(turn, (list, tuple)) and len(turn) == 2:
                # Format cũ: [user_turn, bot_turn]
                user_turn, bot_turn = turn
                if user_turn:
                    history_text += f"User: {user_turn}\n"
                if bot_turn:
                    history_text += f"Assistant: {bot_turn}\n"

    prompt = f"""You are a knowledgeable and helpful financial assistant.
Answer the user's query clearly and accurately based on the context data provided.
- Use the data in 'database_info' to answer factual questions.
- If the context indicates errors or missing data, acknowledge it gracefully.
- Answer in the same language as the user's query (Vietnamese or English).
- Do not make up information not present in the context.
{history_text}
User's query: "{original_user_query}"

Available context data (JSON):
```json
{context_json}
```

Provide your response:"""

    print(f"  Response Synthesizer: Generating final answer...")

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.6)
        )

        answer = response.text.strip() if response.text else ""
        print(f"  Response Synthesizer: Done. Preview: '{answer[:100]}...'")
        return answer

    except Exception as e:
        import traceback
        traceback.print_exc()
        return "Sorry, an error occurred while generating a response."