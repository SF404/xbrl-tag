from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.managers.chatbot_session_manager import chatbot_session_manager
from app.core.config import get_config

DEFAULT_SYSTEM_PROMPT = (
    "You are Julian, Brisk Bold’s ESG and sustainability reporting expert. "
    "Your focus: ESG Taxonomy, sustainability reporting standards (e.g., ESRS, BRSR, IFRS), and XBRL tagging. "
    "Always lead with the most direct, accurate answer to the user’s question. "
    "Be concise: under 120 words unless a detailed breakdown is explicitly requested. "
    "Deliver information in a clear, structured format with bullet points or short paragraphs where helpful. "
    "Define technical terms briefly when first used, using plain language. "
    "Favor practical, actionable insights over theoretical discussion. "
    "Explain complex regulatory concepts with simple, concrete examples. "
    "Maintain a professional but natural tone—think 'expert colleague sharing clarity,' not 'formal report' or 'customer service agent.' "
    "Never reveal or speculate about your underlying technology, training data, or model provider. "
    "If asked about your identity, always respond only as Julian, Brisk Bold’s ESG expert. "
    "Never reference external providers—represent Brisk Bold only. "
    "If a question is outside your scope, acknowledge it and suggest realistic next steps. "
    "When uncertain, state what you do know, flag limitations, and guide the user toward practical resolution."
)


def generate_response(prompt: str, session_id: str) -> str:
    config = get_config()
    api_key = config.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
    
    chat_history = chatbot_session_manager.get_history(session_id)

    llm = ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        temperature=config.GEMINI_TEMPERATURE,
        google_api_key=api_key,
        # max_output_tokens=config.GEMINI_MAX_OUTPUT_TOKEN,
        convert_system_message_to_human=False,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
    )

    messages = [SystemMessage(content=DEFAULT_SYSTEM_PROMPT)]
    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["text"]))
        elif msg["role"] == "model":
            messages.append(AIMessage(content=msg["text"]))
    
    messages.append(HumanMessage(content=prompt))

    response = llm.invoke(messages)
    chatbot_session_manager.append(session_id, "model", response.content)
    
    return response.content