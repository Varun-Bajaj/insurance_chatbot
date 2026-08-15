from fastapi import Request, Body, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import Response
from logs.logger_setup import setup_logger
import urllib
import urllib.parse
import json
from json.decoder import JSONDecodeError


api_logger = setup_logger("api_logger")
app_logger = setup_logger("app_logger")
resp_logger = setup_logger("resp_logger")



async def log_requests(request: Request, call_next):
    try:
        api_logger.info("ip address: {}, request path: {}, parameters: {}"
                        .format(request.client.host, request.url.path,
                                urllib.parse.unquote(request.url.query).replace("+", " ")))
        response = await call_next(request)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        if request.url.path not in ['/docs', '/openapi.json']:
            try:
                # 🔹 Check if response is binary (image, video, etc.)
                if response.media_type and ("image" in response.media_type or "video" in response.media_type):
                    resp_logger.info("Binary response detected. Skipping logging for: {}".format(request.url.path))
                else:
                    # Attempt to decode & log JSON/text responses
                    decoded_body = body.decode("utf-8")  # Decode safely
                    try:
                        json_body = json.dumps(json.loads(decoded_body), indent=4)
                    except JSONDecodeError:
                        json_body = decoded_body  # If not JSON, log raw text

                    resp_logger.info("ip address: {}, request path: {}, parameters: {}, response: \n{}"
                                     .format(request.client.host, request.url.path,
                                             urllib.parse.unquote(request.url.query).replace("+", " "),
                                             json_body))


            except Exception as e:
                api_logger.exception(f"Exception in {request.url.path} response: {str(e)}")

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
    except Exception as e:
        api_logger.exception(f"Exception in {e}")
    return None