from fastapi import HTTPException, APIRouter
from app.schemas.schemas import ChatRequest, ChatResponse
from app.services import generate_response

router = APIRouter(prefix="/chatbot")

@router.post("/generate", response_model=ChatResponse)
async def generate_text(request: ChatRequest):
    try:
        response_text = generate_response(request.prompt)
        return ChatResponse(text=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))