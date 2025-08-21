from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import FileResponse
from app.services.audio_service import (
    process_audio_paid,
    check_openai_api_key,
    process_resume_upload
)
from app.schemas.response_schemas import api_response
from app.utils.util import HTML_TEMPLATE_STRING
import openai


router = APIRouter()

# @router.get("/check-api-key", response_model=api_response)
# def check_api_key():
#     result = check_openai_api_key()
#     return result

@router.post("/upload-resume", response_model=api_response)
async def upload_resume(
    file: UploadFile = File(...),
    client_id: str = Form(...)
):
    result = await process_resume_upload(file, client_id)
    return result


@router.post("/process-audio", response_model=api_response)
async def process_paid_audio(
    file: UploadFile = File(...),
    client_id: str = Form(...)
):
    result = await process_audio_paid(file, client_id)
    return result


@router.get("/generate-sample-audio")
async def generate_sample_audio():
    try:
        # Generate audio using OpenAI TTS
        response = openai.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input="Hello! Can you please explain about yourself"
        )

        # Save the audio file locally
        sample_file = "sample.mp3"
        with open(sample_file, "wb") as f:
            f.write(response.content)

        # Return the file as a response
        return FileResponse(sample_file, media_type="audio/mpeg", filename="sample.mp3")

    except Exception as e:
        return {"error": str(e)}
    
