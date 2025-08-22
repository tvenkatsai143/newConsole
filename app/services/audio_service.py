import io
import os
import tempfile
from faster_whisper import WhisperModel
from fastapi import UploadFile
import openai
from app.core.config import OPENAI_API_KEY
from app.schemas.response_schemas import api_response
from http import HTTPStatus

openai.api_key = OPENAI_API_KEY
whisper_model = WhisperModel("tiny.en", compute_type="int8")  # or "base.en" for better accuracy

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



# RESUME_CONTEXT = ""  # Will hold summarized resume context
RESUME_CONTEXT = {}  # key: client_id, value: summarized resume
import fitz

# -----------------------------
# 1. Resume Upload API
# -----------------------------
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

# ---------------------- 31-07-2025 ----------------------------------
# async def process_resume_upload(file, client_id):
#     global RESUME_CONTEXT
#     try:
#         resume_text = await extract_text_from_pdf(file)
#         RESUME_CONTEXT = await summarize_resume(resume_text)

#         return api_response(
#             responseCode=HTTPStatus.OK,
#             message="Resume uploaded and summarized successfully.",
#             payLoad={"resume_summary": RESUME_CONTEXT}
#         )
#     except Exception as e:
#         return api_response(
#             responseCode=HTTPStatus.INTERNAL_SERVER_ERROR,
#             message=f"Failed to process resume: {str(e)}",
#             payLoad=None
#         )


async def process_resume_upload(file, client_id):
    global RESUME_CONTEXT
    try:
        resume_text = await extract_text_from_pdf(file)
        summary = await summarize_resume(resume_text)

        # Store resume context against the client_id
        RESUME_CONTEXT[client_id] = summary
        print("resume",RESUME_CONTEXT)
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

# -----------------------------------------------------
# 2. Updated process interview question in audio file
# -----------------------------------------------------
async def process_audio_paid(audio_io: io.BytesIO, client_id):
    print("=================")
    # print(f"Number of users in memory: {len(RESUME_CONTEXT)}")
    try:
        # audio_bytes = await file.read()
        # audio_stream = io.BytesIO(audio_bytes)

        # transcript = openai.audio.transcriptions.create(
        #     model="whisper-1",
        #     file=("audio.wav", audio_stream),
        #     language="en",
        #     response_format="verbose_json"
        # )
        # transcribed_text = transcript.text.strip()
        # language = transcript.language

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            temp_audio.write(audio_io.read())
            temp_audio_path = temp_audio.name  # Store path to reopen it

        # Now file is closed — safe for FFmpeg to access
        segments, info = whisper_model.transcribe(temp_audio_path)
        #transcribed_text = " ".join([seg.text for seg in segments]).strip()
        language = info.language
        # Clean up temp file
        os.remove(temp_audio_path)
        transcribed_text = """Full-Stack Developer with 3+ years of experience in building scalable web, mobile, and IoT solutions using Angular, Vue.js, React.js, .NET Core, C#, SQL, PostgreSQL, and Microsoft Azure. Strong expertise in cloud automation, IoT-based applications, financial tech tools, and real-time dashboards. Skilled at integrating APIs, automating workflows, and delivering optimized, secure, and maintainable solutions.

        Key Experience:
        - Developed and maintained web & mobile apps using Angular, Vue.js, and .NET Core.
        - Designed and deployed IoT-based temperature monitoring systems with Azure integration for real-time alerts.
        - Built Azure Functions & Service Bus pipelines for automated data handling and notifications.
        - Integrated Telegram & Angel One APIs for financial and alerting applications.
        - Engineered a stock screener tool using RSI/MACD logic with automated Telegram alerts.
        - Created real-time dashboards and reporting tools for analytics.

        Projects:
        - Chef Worksheet & Menu Management System – Cross-platform solution (Angular for web, Vue.js for mobile) powered by a single .NET Core Web API ensuring consistency and reusability.
        - IoT Temperature Monitoring System – Captured and processed live temperature data from food storage containers with Azure-triggered alerts.
        - Automated Stock Alert System – Developed with .NET 6, Azure Cosmos DB, and custom C# algorithms, integrating RSI, MACD, support/resistance, and Telegram Bot for automated stock alerts.

        Skills:
        - Frontend: Angular, Vue.js, React.js, HTML, CSS
        - Backend: .NET Core, C#
        - Cloud & DevOps: Azure Cloud, Azure DevOps, Azure Functions, Service Bus, Cosmos DB
        - Databases: SQL, PostgreSQL
        - Others: API integration, real-time dashboards, automation
        """

        # if not transcribed_text:
        #     return api_response(
        #         responseCode=HTTPStatus.BAD_REQUEST,
        #         message="No speech detected in the audio.",
        #         payLoad=None
        #     )
        # Fetch resume context for the client_id
        # resume_context =None
        # if(RESUME_CONTEXT == {}):
        #     return {
        #     "transcribed_text": None,
        #     "language": language,
        #     "ai_response": "Resume context not found. Please upload the resume first"
        #     }
        # resume_context = RESUME_CONTEXT.get(client_id)
        # if not resume_context:
        #     return {
        #     "transcribed_text": None,
        #     "language": language,
        #     "ai_response": "Resume context not found. Please upload the resume first"
        #     }
        print("resume",RESUME_CONTEXT)
        resume_context = RESUME_CONTEXT.get(client_id)
        if not resume_context:
            return {
            "transcribed_text": None,
            "language": language,
            "ai_response": "Resume context not found. Please upload the resume first"
            }

        # Prepare user prompt with resume context
        # user_prompt = f"Resume Context:\n{RESUME_CONTEXT}\n\nInterview Question: {transcribed_text}"
        # if language != "en":
        #     user_prompt += "\n\nPlease respond in English."

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

        # response = {
        #     "transcribed_text": transcribed_text,
        #     # "language": language,
        #     "ai_response": response_text
        # }

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

# -----------------------------
# 3. Updated process_audio_paid_ws
# -----------------------------
async def process_audio_paid_ws(audio_io: io.BytesIO):
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            temp_audio.write(audio_io.read())
            temp_audio_path = temp_audio.name  # Store path to reopen it

        # Now file is closed — safe for FFmpeg to access
        segments, info = whisper_model.transcribe(temp_audio_path)
        transcribed_text = " ".join([seg.text for seg in segments]).strip()
        language = info.language

        # Clean up temp file
        os.remove(temp_audio_path)
        if not transcribed_text:
            return {"error": "No speech detected in the audio."}
# gpt-3.5-turbo
        # Add resume context
        user_prompt = f"Resume Context:\n{RESUME_CONTEXT}\n\nInterview Question: {transcribed_text}"
        if language != "en":
            user_prompt += "\n\nPlease respond in English."

        gpt_response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
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


async def logout_user(client_id):
    try:
        if client_id in RESUME_CONTEXT:
            del RESUME_CONTEXT[client_id]
            return api_response(
                responseCode=HTTPStatus.OK,
                message="User logged out successfully and resume context cleared.",
                payLoad=None
            )
        else:
            return api_response(
                responseCode=HTTPStatus.NOT_FOUND,
                message="Client ID not found.",
                payLoad=None
            )
    except Exception as e:
        return api_response(
            responseCode=HTTPStatus.INTERNAL_SERVER_ERROR,
            message=f"An unexpected error occurred: {str(e)}",
            payLoad=None
        )