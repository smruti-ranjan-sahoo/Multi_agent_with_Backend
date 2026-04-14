import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import UploadedFile, Conversation
from app.core.security import verify_access_token
from app.services.rag.rag_services import rag_service

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ALLOWED_TYPES = {"pdf", "csv"}
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10MB


# ── Upload & Index File ────────────────────────────
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    # auth check
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # file type check
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type '.{ext}' not supported. Use PDF or CSV.")

    # read file bytes
    file_bytes = await file.read()

    # file size check
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size is 10MB.")

    # namespace = conversation_id (isolates vectors per conversation)
    namespace = f"conv_{conversation_id}"

    # index into Pinecone
    result = await rag_service.index_document(
        file_bytes=file_bytes,
        filename=file.filename,
        namespace=namespace
    )

    # save file record to DB
    uploaded = UploadedFile(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        file_name=file.filename,
        file_type=ext,
        cloudinary_url=None,   # Phase 5 — multimodal
    )
    db.add(uploaded)
    await db.commit()
    await db.refresh(uploaded)

    return {
        "file_id": str(uploaded.id),
        "filename": file.filename,
        "chunks_indexed": result["chunks"],
        "namespace": namespace,
        "status": "ready"
    }


# ── RAG Query ─────────────────────────────────────
@router.post("/query")
async def query_document(
    conversation_id: str,
    question: str,
    provider: str = "groq",
    model: str = None,
    token: str = Depends(oauth2_scheme),
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    namespace = f"conv_{conversation_id}"

    answer = await rag_service.query(
        question=question,
        namespace=namespace,
        provider=provider,
        model=model
    )

    return {
        "question": question,
        "answer": answer,
        "namespace": namespace
    }


# ── Delete File Vectors ────────────────────────────
@router.delete("/delete/{conversation_id}")
async def delete_vectors(
    conversation_id: str,
    token: str = Depends(oauth2_scheme),
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    namespace = f"conv_{conversation_id}"
    await rag_service.delete_document(namespace)
    return {"status": "deleted", "namespace": namespace}