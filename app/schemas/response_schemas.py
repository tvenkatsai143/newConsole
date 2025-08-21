from http import HTTPStatus
from typing import Any, Optional
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel


def api_response(
    responseCode: int = HTTPStatus.OK,
    message: Optional[str] = None,
    payLoad: Optional[Any] = None
) -> JSONResponse:
    return JSONResponse(
        content={
            "statusCode": responseCode,
            "message": message,
            "payLoad": jsonable_encoder(payLoad)
        },
        status_code=responseCode
    )


class LoginRequest(BaseModel):
    email: str
    password: str

# class FileUploadRequest(BaseModel):
#     file: 
#     client_id: str