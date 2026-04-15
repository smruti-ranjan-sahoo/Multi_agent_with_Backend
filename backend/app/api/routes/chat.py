from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
import base64
from groq import AsyncGroq
from app.agents.agent_service import agent_service
from app.services.llm.factory import get_llm_provider, get_supported_providers
from app.services.rag.rag_services import rag_service
from app.services.audio_service import get_audio_service
from app.core.security import verify_access_token
from app.core.config import settings, get_models_for_provider
from app.agents.tools.web_search import get_search_diagnostics

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


VISION_MODEL_PREFERENCES = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-4-maverick-17b-128e-instruct",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
]


def _get_auto_vision_model(requested_model: Optional[str] = None) -> str:
    available = settings.GROQ_MODELS

    # If requested model is explicitly a known vision-capable model and available, use it.
    if requested_model and requested_model in VISION_MODEL_PREFERENCES and requested_model in available:
        return requested_model

    # Otherwise auto-select best available vision model.
    for model in VISION_MODEL_PREFERENCES:
        if model in available:
            return model

    raise HTTPException(
        status_code=400,
        detail="No vision model configured. Add a Groq vision model in GROQ_MODELS."
    )


def _get_vision_candidates(requested_model: Optional[str] = None) -> list[str]:
    candidates: list[str] = []

    # User-requested model gets highest priority.
    if requested_model:
        candidates.append(requested_model)

    # Known preferred model IDs and aliases.
    for m in VISION_MODEL_PREFERENCES:
        if m not in candidates:
            candidates.append(m)

    # Configured models that look vision-capable.
    for m in settings.GROQ_MODELS:
        lower = m.lower()
        if "vision" in lower or "llama-4" in lower:
            if m not in candidates:
                candidates.append(m)

    return candidates


# ── Request Schemas ────────────────────────────────
class ChatRequest(BaseModel):
    messages:        list[dict]
    provider:        str           = "groq"
    model:           Optional[str] = None
    stream:          bool          = False
    conversation_id: str           = "default"
    usecase:         str           = "auto"
    has_documents:   bool          = False
    namespace:       str           = ""        # ← NEW

class NamespaceRequest(BaseModel):
    namespace: str


class TextToSpeechRequest(BaseModel):
    text: str
    voice: str = "alloy"
    speed: float = 1.0
    language: str = "en"


class SpeechToTextRequest(BaseModel):
    language: str = "en"
    prompt: Optional[str] = None


class WebSearchDiagnosticsRequest(BaseModel):
    query: str
    max_results: int = 5


# ── Send Message ───────────────────────────────────
@router.post("/send")
async def send_message(
    req: ChatRequest,
    token: str = Depends(oauth2_scheme)
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    llm = get_llm_provider(req.provider)
    available_models = llm.get_available_models()
    default_model = settings.__dict__.get(
        f"DEFAULT_{req.provider.upper()}_MODEL",
        settings.DEFAULT_GROQ_MODEL
    )
    model = req.model or default_model
    if model not in available_models:
        model = default_model if default_model in available_models else available_models[0]

    if req.stream:
        async def generator():
            async for chunk in llm.stream_chat(req.messages, model):
                yield chunk
        return StreamingResponse(generator(), media_type="text/plain")

    result = await agent_service.run(
        user_message=req.messages[-1]["content"],
        user_id=user_id,
        conversation_id=req.conversation_id,
        provider=req.provider,
        model=model,
        usecase=req.usecase,
        has_documents=req.has_documents,
        namespace=req.namespace,               # ← NEW
    )
    return result


# ── Upload Document ────────────────────────────────
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    namespace: str = Form(...),
    token: str = Depends(oauth2_scheme)
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    file_bytes = await file.read()
    result = await rag_service.index_document(
        file_bytes=file_bytes,
        filename=file.filename,
        namespace=namespace
    )
    return result


# ── Delete Namespace ───────────────────────────────
@router.post("/delete-namespace")
async def delete_namespace(
    req: NamespaceRequest,
    token: str = Depends(oauth2_scheme)
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return await rag_service.delete_document(req.namespace)


# ── Get Available Models ───────────────────────────
@router.get("/models")
async def get_models(
    provider: str = "groq",
    token: str = Depends(oauth2_scheme)
):
    verify_access_token(token)
    models = get_models_for_provider(provider)
    return {"provider": provider, "models": models}


# ── Get All Providers ──────────────────────────────
@router.get("/providers")
async def get_providers(token: str = Depends(oauth2_scheme)):
    verify_access_token(token)
    return {"providers": get_supported_providers()}


# ── Web Search Diagnostics ──────────────────────────
@router.post("/web-search-diagnostics")
async def web_search_diagnostics(
    req: WebSearchDiagnosticsRequest,
    token: str = Depends(oauth2_scheme)
):
    verify_access_token(token)
    max_results = max(1, min(req.max_results, 10))
    return await get_search_diagnostics(req.query, max_results=max_results)


# ── Audio: Speech-to-Text ──────────────────────────
@router.post("/speech-to-text")
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = Form("en"),
    prompt: Optional[str] = Form(None),
    token: str = Depends(oauth2_scheme)
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        audio_bytes = await file.read()
        audio_service = get_audio_service()
        return await audio_service.speech_to_text(
            audio_bytes,
            language=language,
            prompt=prompt
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Audio: Text-to-Speech ──────────────────────────
@router.post("/text-to-speech")
async def text_to_speech(
    req: TextToSpeechRequest,
    token: str = Depends(oauth2_scheme)
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        audio_service = get_audio_service()
        return await audio_service.text_to_speech(
            text=req.text,
            voice=req.voice,
            speed=req.speed,
            language=req.language
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Audio: Available Voices ────────────────────────
@router.get("/audio/voices")
async def get_voices(token: str = Depends(oauth2_scheme)):
    verify_access_token(token)
    audio_service = get_audio_service()
    return {"voices": audio_service.get_available_voices()}


# ── Audio: Available Languages ────────────────────
@router.get("/audio/languages")
async def get_languages(token: str = Depends(oauth2_scheme)):
    verify_access_token(token)
    audio_service = get_audio_service()
    return {"languages": audio_service.get_available_languages()}


# ── Vision: Ask About Image ───────────────────────
@router.post("/vision/ask")
async def ask_about_image(
    file: UploadFile = File(...),
    question: str = Form(...),
    model: Optional[str] = Form(None),
    token: str = Depends(oauth2_scheme)
):
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty")

        selected_model = _get_auto_vision_model(model)
        mime_type = file.content_type or "image/png"
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_data_url = f"data:{mime_type};base64,{image_b64}"

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        last_error = ""
        used_model = selected_model

        for candidate_model in _get_vision_candidates(model):
            try:
                completion = await client.chat.completions.create(
                    model=candidate_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": question},
                                {"type": "image_url", "image_url": {"url": image_data_url}},
                            ],
                        }
                    ],
                    temperature=0.2,
                )

                answer = ""
                if completion.choices and completion.choices[0].message:
                    answer = completion.choices[0].message.content or ""

                if not answer:
                    answer = "I could not generate an answer from this image. Please try another image or question."

                used_model = candidate_model
                return {
                    "response": answer,
                    "question": question,
                    "model": used_model,
                    "status": "ok"
                }
            except Exception as model_err:
                err_text = str(model_err)
                last_error = err_text
                lowered = err_text.lower()
                # Retry only when model is invalid/decommissioned/not accessible.
                if (
                    "model_not_found" in lowered
                    or "decommissioned" in lowered
                    or "no longer supported" in lowered
                    or "do not have access" in lowered
                    or "messages[0].content must be a string" in lowered
                    or "content must be a string" in lowered
                ):
                    continue
                raise HTTPException(status_code=500, detail=err_text)

        raise HTTPException(
            status_code=400,
            detail=f"No working vision model found for this account. Last error: {last_error}"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


# ── Image Generation (Pollinations - Free, no API key) ───────────────────


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str = "pollinations"
    height: int = 768
    width: int = 768


@router.get("/image-generation/models")
async def get_image_generation_models(token: str = Depends(oauth2_scheme)):
    """Get available free image generation models"""
    from app.services.image_generation_service import AVAILABLE_MODELS
    verify_access_token(token)
    return {
        "models": AVAILABLE_MODELS,
        "provider": "pollinations",
        "free_tier": True
    }


@router.post("/image-generation/generate")
async def generate_image(
    request: ImageGenerationRequest,
    token: str = Depends(oauth2_scheme)
):
    """
    Generate an image using Pollinations (free, no API key)
    """
    from app.services.image_generation_service import get_available_models, generate_image

    # Verify user
    verify_access_token(token)

    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if len(request.prompt) > 1000:
        raise HTTPException(status_code=400, detail="Prompt too long (max 1000 characters)")

    # Generate image
    result = await generate_image(
        prompt=request.prompt,
        model_key=request.model,
        height=request.height,
        width=request.width,
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Image generation failed")
        )

    return {
        "success": True,
        "images": result["image_urls"],
        "prompt": request.prompt,
        "model": request.model,
    }