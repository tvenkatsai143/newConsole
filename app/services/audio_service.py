from datetime import timedelta
import io
import json
import os
import tempfile
from fastapi import UploadFile
import openai
from app.schemas.response_schemas import api_response
from http import HTTPStatus
import fitz
import redis
# from faster_whisper import WhisperModel
from dotenv import load_dotenv
import json

load_dotenv()
# whisper_model = WhisperModel("tiny.en", compute_type="int8")  # or "base.en" for better accuracy
openai.api_key = os.getenv("OPENAI_API_KEY", )
RESUME_CONTEXT = {}

# redis_client = redis.Redis(host='localhost', port=6379, db=0)
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    db=os.getenv("REDIS_DB"),
    password=os.getenv("REDIS_PASSWORD")
)


# --- Check OpenAI Keys ---
def check_openai_api_key():
    if not openai.api_key:
        return api_response(responseCode=HTTPStatus.NOT_FOUND, message="OPENAI_API_KEY not found in environment variables", payLoad=None)
    try:
        response = openai.models.list()
        models = [model.id for model in response.data]
        response = {
            "status": "API Key is valid!",
            "available_models": models
        }
        return api_response(responseCode=HTTPStatus.OK, message="API key status", payLoad=response)
    except Exception as e:
        return api_response(
            responseCode=HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"An Exception Occurred {str(e)}",
            payLoad=None
        )


async def extract_text_from_pdf(file: UploadFile) -> str:
    pdf = fitz.open(stream=await file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    return text.strip()

async def summarize_resume(resume_text: str) -> str:
    """
    Summarize resume text using OpenAI for faster responses.
    """
    gpt_response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert resume summarizer."},
            {"role": "user", "content": f"Summarize this resume focusing on skills, projects, and experience:\n\n{resume_text}"}
        ]
    )
    return gpt_response.choices[0].message.content.strip()

# Resume Upload API

# Resume Upload API
async def process_resume_upload(file: UploadFile, client_id: str):
    try:
        # Step 1: Extract and summarize resume
        resume_text = await extract_text_from_pdf(file)
        summary = await summarize_resume(resume_text)

        # Step 2: Save to Redis with 90-minute expiry
        redis_key = f"resume:{client_id}"
        # redis_client.setex(redis_key, timedelta(minutes=90), summary)
        expiry_seconds = int(timedelta(minutes=90).total_seconds()) 
        redis_client.setex(redis_key, expiry_seconds, summary)

        return api_response(
            responseCode=HTTPStatus.OK,
            message="Resume uploaded and summarized successfully.",
            payLoad={"resume_summary": summary}
        )

    except Exception as e:
        return api_response(
            responseCode=HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"Failed to process resume: {str(e)}",
            payLoad=None
            )



async def process_audio_paid(audio_io: io.BytesIO, client_id):
    transcribed_text = None
    language = None
    try:        
       # Set the correct filename and extension for the BytesIO buffer
        audio_io.name = "audio.webm"  # ✅ Tells OpenAI the format

        # Now pass just the file-like object (no tuple)
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_io,
            language="en",
            response_format="verbose_json"
        )


        transcribed_text = transcript.text.strip()
        language = getattr(transcript, "language", "en")
        # transcribed_text = transcript.text.strip()

        if not transcribed_text:
            return api_response(
                responseCode=HTTPStatus.BAD_REQUEST,
                message="No speech detected in the audio.",
                payLoad=None
            )

        # Checking cached response in Redis

        # Fetch resume context from Redis
        redis_key = f"resume:{client_id}"
        resume_context = redis_client.get(redis_key)
        if not resume_context:
           return {
            "transcribed_text": None,
            "language": language,
            "ai_response": "Resume context not found. Please upload the resume first"
            }

        # Redis returns bytes, decode to string
        resume_context = resume_context.decode('utf-8')
        # Asking OpenAI for interview response
        gpt_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a job candidate attending an interview. "
                        "Respond naturally and professionally as if you're speaking directly to the interviewer. "
                        "Base your answers on the resume provided."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Here's my resume:\n{resume_context}\n\n"
                        f"I was asked the following interview question:\n"
                        f"{transcribed_text}\n\n"
                        f"Please respond like I would in a real interview."
                    )
                }
            ],
        )
        response_text = gpt_response.choices[0].message.content
        # Cache the response in Redis
        # redis_client.set(cache_key, json.dumps(response), ex=60 * 60)  # cache for 1 hour

        return {
            "transcribed_text": transcribed_text,
            "language": language,
            "ai_response": response_text
        }

    except Exception as e:
        return {
            "transcribed_text": transcribed_text,
            "language": language,
            "ai_response": f"An Exception Occurred: {str(e)}"
        }

# Updated process_audio_paid_ws
async def process_audio_paid_ws(audio_data, filename, websocket):
    temp_file = f"temp_{filename}"
    try:
        with open(temp_file, "wb") as f:
            f.write(audio_data)

        with open(temp_file, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
                response_format="verbose_json"
            )
        transcribed_text = transcript.text.strip()
        language = transcript.language

        os.remove(temp_file)

        if not transcribed_text:
            return {"error": "No speech detected in the audio."}

        # Add resume context
        user_prompt = f"Resume Context:\n{RESUME_CONTEXT}\n\nInterview Question: {transcribed_text}"
        if language != "en":
            user_prompt += "\n\nPlease respond in English."

        gpt_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a candidate answering questions based on the resume context."},
                {"role": "user", "content": user_prompt},
            ],
        )
        response_text = gpt_response.choices[0].message.content

        return {
            "transcribed_text": transcribed_text,
            "language": language,
            "ai_response": response_text
        }

    except Exception as e:
        return api_response(responseCode=HTTPStatus.INTERNAL_SERVER_ERROR, message=f"An Expected error occured {str(e)}", payLoad = None)


# async def logout_user(client_id):
#     try:
    
#         # Delete from Redis
#         redis_key = f"resume:{client_id}"
#         redis_deleted = redis_client.delete(redis_key)

#         return api_response(
#             responseCode=HTTPStatus.OK,
#             message="User logged out successfully. Resume context and Redis key deleted.",
#             payLoad={"redis_deleted": bool(redis_deleted)}
#         )

#     except Exception as e:
#         return api_response(
#             responseCode=HTTPStatus.INTERNAL_SERVER_ERROR,
#             message=f"An unexpected error occurred: {str(e)}",
#             payLoad=None
#         )

async def logout_user(client_id):
    try:
        # Delete main resume key
        resume_key = f"resume:{client_id}"
        redis_client.delete(resume_key)

        # Find and delete all question-related keys for this client
        pattern = f"{client_id}:*"
        keys_to_delete = []
        cursor = 0

        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match=pattern)
            keys_to_delete.extend(keys)
            if cursor == 0:
                break

        if keys_to_delete:
            redis_client.delete(*keys_to_delete)

        return api_response(
            responseCode=HTTPStatus.OK,
            message="User logged out successfully. All Redis keys deleted.",
            payLoad={"deleted_keys": [resume_key] + keys_to_delete}
        )

    except Exception as e:
        return api_response(
            responseCode=HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"An unexpected error occurred: {str(e)}",
            payLoad=None
        )