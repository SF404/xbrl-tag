from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends

from app.managers.chatbot_session_manager import chatbot_session_manager
# from app.core.deps import require_access_level
from app.schemas.schemas import ChatRequest, ChatResponse
from app.services import generate_response

router = APIRouter(prefix="/chatbot")

# async def generate_text(chat_request: ChatRequest,  _=Depends(require_access_level(7)),

@router.post("/generate", response_model=ChatResponse)
async def generate_text(chat_request: ChatRequest):
    """
    Generates a chatbot response based on a user's prompt.

    It maintains a session history. If no session_id is provided, a new one
    is created.
    """
    try:
        # Ensure a session ID exists, creating one if necessary
        session_id = chat_request.session_id or str(uuid4())

        response_text = generate_response(chat_request.prompt, session_id)

        return ChatResponse(text=response_text, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear/{session_id}")
async def clear_session(session_id: str):
    """
    Clears the chat history for a given session ID.
    """
    chatbot_session_manager.clear(session_id)
    return {"message": f"Session {session_id} cleared."}

