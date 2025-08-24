from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from datetime import datetime
from typing import List
import os
from dotenv import load_dotenv

from app.auth import authenticate_user, create_access_token, get_current_user, create_user
from app.models import UserCreate, User, QuestionRequest
from app.database import get_db, init_db
from app.rag_system import RAGSystem
from app.chat_history import ChatHistoryManager

load_dotenv()

app = FastAPI(
    title="Healthcare AI Assistant",
    description="FastAPI backend with authentication and RAG system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock this down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize systems
rag_system = RAGSystem()
chat_manager = ChatHistoryManager()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    init_db()
    print("🚀 Healthcare AI FastAPI started successfully!")

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

# Authentication endpoints
@app.post("/auth/register")
async def register(user_data: UserCreate, db=Depends(get_db)):
    try:
        user = create_user(db, user_data)
        return {
            "success": True,
            "message": "User registered successfully",
            "user_id": user.id
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name
        }
    }

@app.get("/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

# Document endpoints
@app.post("/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    try:
        os.makedirs("storage", exist_ok=True)
        processed_files = []
        for file in files:
            if file.content_type != "application/pdf":
                continue
            file_path = f"storage/{current_user.id}_{file.filename}"
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            doc_id = await rag_system.process_document(file_path, current_user.id)
            processed_files.append({
                "filename": file.filename,
                "document_id": doc_id,
                "status": "processed"
            })
        return {
            "success": True,
            "message": f"Processed {len(processed_files)} documents",
            "documents": processed_files
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing documents: {str(e)}"
        )

@app.get("/documents/list")
async def list_user_documents(current_user: User = Depends(get_current_user)):
    documents = rag_system.get_user_documents(current_user.id)
    return {"documents": documents}

# Chat endpoints
@app.post("/chat/ask")
async def ask_question(
    question_data: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    try:
        response = await rag_system.get_answer(
            question=question_data.question,
            user_id=current_user.id,
            top_k=question_data.top_k or 5
        )

        chat_manager.save_message(
            db=db,
            user_id=current_user.id,
            message=question_data.question,
            response=response["answer"],
            sources=response.get("sources", [])
        )

        return {
            "success": True,
            "answer": response["answer"],
            "sources": response.get("sources", []),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )

@app.get("/chat/history")
async def get_chat_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    history = chat_manager.get_user_history(db, current_user.id, limit)
    return {"history": history}

@app.delete("/chat/clear")
async def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    chat_manager.clear_user_history(db, current_user.id)
    return {"message": "Chat history cleared successfully"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    uvicorn.run("main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")), reload=True)
