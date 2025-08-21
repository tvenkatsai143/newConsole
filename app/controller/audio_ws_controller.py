from io import BytesIO
from fastapi import APIRouter, WebSocket
from app.services.audio_service import process_audio_paid
from azure.webpubsub import WebPubSubServiceClient

router = APIRouter()
import os
WebPub = os.getenv("WebPubService")

# Initialize Azure Web PubSub client
service = WebPubSubServiceClient.from_connection_string(WebPub, hub="interview-hub"
)


@router.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket,client_id : str):
    await websocket.accept()
    audio_buffer = BytesIO()
    try:
        while True:
            message = await websocket.receive()
            if "text" in message and message["text"] == "stop":
                break
            elif "bytes" in message:
                audio_buffer.write(message["bytes"])

        audio_buffer.seek(0)

        # Process audio and return result
        result = await process_audio_paid(audio_buffer,client_id)

        await websocket.send_json({
            "status": "completed",
            "data": result
        })

    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        await websocket.close()
        print("🔌 WebSocket closed")