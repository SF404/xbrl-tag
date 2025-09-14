from fastapi import HTTPException, APIRouter
from app.schemas.schemas import ChatRequest, ChatResponse
from app.managers.chatbot_session_manager import chatbot_session_manager
from app.services import generate_response
from uuid import uuid4

router = APIRouter(prefix="/chatbot")

@router.post("/generate", response_model=ChatResponse)
async def generate_text(request: ChatRequest):
    try:
        session_id = request.session_id if request.session_id else str(uuid4())
        response_text = generate_response(request.prompt, session_id)

        return ChatResponse(text=response_text, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
    
@router.delete("/clear/{session_id}")
async def clear_session(session_id: str):
    chatbot_session_manager.clear(session_id)
    return {"message": f"Session {session_id} cleared."}

