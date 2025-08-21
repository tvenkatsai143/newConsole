from io import BytesIO
import secrets
import subprocess
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from html2docx import html2docx
import redis
from app.controller.audio_controller import router as audio_router
from app.controller.audio_ws_controller  import router as audio_router_ws
from app.schemas.response_schemas import LoginRequest, api_response
from http import HTTPStatus

from app.services.audio_service import logout_user
from app.utils.template_code import HTML_CODE
from app.utils.util import HTML_TEMPLATE_STRING
import os
from dotenv import load_dotenv

REDIS_URL = os.getenv("REDIS_URL")
r = redis.from_url(REDIS_URL, decode_responses=True)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


app = FastAPI(title="AI Interview Assistance")

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ffmpeg_path = os.path.join(os.path.dirname(__file__), "bin")
# os.environ["PATH"] = ffmpeg_path + ":" + os.environ["PATH"]

# @app.get("/ffmpeg-version")
# def ffmpeg_version():
#     result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
#     return {"output": result.stdout or result.stderr}

@app.get("/")
def read_root():
    r.set("greeting", "Hello from FastAPI on Render!")
    return {"msg": r.get("greeting")}

@app.post("/app/login")
def login(request: LoginRequest):
    try:
        print(ADMIN_EMAIL,ADMIN_PASSWORD)
        if request.email == ADMIN_EMAIL and request.password == ADMIN_PASSWORD:
            # Generate a small token (random hex string)
            token = secrets.token_hex(16)
            return api_response(responseCode=HTTPStatus.OK, message="Login successful", payLoad= token)
        else:
            return api_response(responseCode=HTTPStatus.UNAUTHORIZED, message="Invalid email or password", payLoad = None)
    except Exception as e:
        return api_response(responseCode=HTTPStatus.INTERNAL_SERVER_ERROR, message=f"An Expected error occured {str(e)}", payLoad = None)


@app.post("/app/logout")
async def logout(client_id: str = Query(...)):
    result = await logout_user(client_id)
    return result



@app.get("/get-template-docx")
def get_docx():
    try:
        # Create a BytesIO buffer
        output_buffer = BytesIO()

        # Convert HTML to DOCX and write to buffer
        docx_bytes_io = html2docx(HTML_TEMPLATE_STRING, output_buffer)

        # Get byte data
        docx_byte_data = docx_bytes_io.getvalue()

        return StreamingResponse(
            content=BytesIO(docx_byte_data),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=document.docx"}
        )
    except Exception as e:
        return {"error": str(e)}

# Include audio router
app.include_router(audio_router, prefix="/audio", tags=["Audio"])
app.include_router(audio_router_ws, prefix="/audio-ws", tags=["Audio WS"])