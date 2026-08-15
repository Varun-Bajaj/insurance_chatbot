from fastapi import Request, Body, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi import FastAPI, Depends, APIRouter
from sqlalchemy.orm import Session
from api.api_v1.endpoints.chatbot_api import is_session_id_valid
import asyncio, json
from utilities.auth_utils import *
from api.deps import get_db
from services import *
from settings.setting import *
from core.error_handler import create_error_dict, create_response
from logs.logger_setup import setup_logger
from dao.chatbot_dao import *
from services.websocket_manager import websocket_manager
from services.Text2SQL_Manager import *

websocket_router = APIRouter(
    prefix = '/ws',
    tags = ["System"],
)

app_logger = setup_logger("app_logger")


@websocket_router.websocket("/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str, db: Session = Depends(get_db)):
    """
    Socket Endpoint for receiving messages
    :param websocket:
    :param session_id:
    :param token:
    :param db:
    :return:
    """
    try:
        await websocket_manager.connect(connection_id=session_id, websocket=websocket)
        try:
            credential = validate_token_from_arguments(token, db=db)
        except:
            print(f"Token is not valid in web socket")
            await websocket_manager.disconnect_connection_web_socket_with_status_code(connection_id=session_id,
                                                                                      status_code=
                                                                                      WEBSOCKET_CLOSE_CODES[
                                                                                          "INVALID_TOKEN"],
                                                                                      reason="Token is Invalid or Expired")
            return
        if not is_session_id_valid(session_id=session_id):
            print(f"Exception session id not valid")
            await websocket_manager.disconnect_connection_web_socket_with_status_code(connection_id=session_id,
                                                                                      status_code=
                                                                                      WEBSOCKET_CLOSE_CODES[
                                                                                          "INVALID_SESSION"],
                                                                                      reason="session_id is Invalid")
            return
        await websocket.send_json({"msg": "ping", "ws_id": session_id})
        while True:
            try:
                data = await websocket.receive_text()
                app_logger.info(f"Received message: {data}")
                data_dict = json.loads(data)
                print(f"Data Dict in web socket: {data_dict}\n Data in web socket {data}")
                # Find a free model
                # available_model = await get_free_model()
                if 'is_session_close' in data_dict:
                    await websocket_manager.disconnect_connection_web_socket_with_status_code(
                        connection_id=session_id,
                        status_code=
                        WEBSOCKET_CLOSE_CODES[
                            "NORMAL_CLOSURE"],
                        reason="Web Socket connection is closed successfully.")
                    app_logger.info(f"web socket disconnect message appear for connection_id {session_id}")
                elif 'is_answer_satisfactory' in data_dict and 'query_id' in data_dict and 'feedback' in data_dict:
                    feedback_data(query_id=data_dict["query_id"], rating=data_dict["is_answer_satisfactory"],
                                  comment=data_dict["feedback"], db=db)
                elif 'query_id' in data_dict:
                    query_id = data_dict['query_id']
                    print(f"WebSocket Query ID: {query_id}")
                    asyncio.create_task(process_query_with_guardrails(credential[1], session_id, query_id, db))
                # elif not available_model:
                #    app_logger.info("No available models. Please wait...")
                elif data_dict:
                    app_logger.info(
                        f"some data has been received from user {credential[1]} having session id {session_id} : {data_dict}")
                    # No model available, inform the client
                    # await websocket.send_text("No available models. Please wait...")
            except json.JSONDecodeError:
                app_logger.info("Invalid JSON data received.")
    except WebSocketDisconnect as e:
        if e.code == 1001:
            print(f"1001 Exception has been occurred in web socket {e}")
            await websocket_manager.disconnect_connection_web_socket_with_status_code(connection_id=session_id,
                                                                                      status_code=
                                                                                      WEBSOCKET_CLOSE_CODES[
                                                                                          "GOING_AWAY"],
                                                                                      reason="Client closed the connection.(page reload)")
            app_logger.info("WebSocket closed with code 1001: Client closed the connection.")
        elif e.code == 1006:
            print(f"1006 Exception has been occurred in web socket {e}")
            await websocket_manager.disconnect_connection_web_socket_with_status_code(connection_id=session_id,
                                                                                      status_code=
                                                                                      WEBSOCKET_CLOSE_CODES[
                                                                                          "ABNORMAL_CLOSURE"],
                                                                                      reason="Web Socket Abnormal disconnection (network issue, crash)")
            app_logger.info("WebSocket closed with code 1006: Abnormal disconnection (network issue, crash).")
        else:
            print(f"Exception has been occcurred in web socket {e}")
            await websocket_manager.disconnect_connection_web_socket_with_status_code(connection_id=session_id,
                                                                                      status_code=e.code,
                                                                                      reason="Web Socket connection is closed successfully.")
            app_logger.exception(f"WebSocket closed with code {e.code}: Unknown reason.")

        app_logger.info(f"web socket disconnected for connection_id {session_id}")
    except RuntimeError as e:
        print(f"runtime Exception has been occurred in web socket {e}")
        # Catch the specific exception and log or handle it
        if "Unexpected ASGI message" in str(e):
            # Handle the situation where websocket.close was attempted after already closing
            pass
        else:
            app_logger.exception(f"Exception {e}")
    except Exception as e:
        print(f"Exception in web socket {e}")
        app_logger.exception(f"exception in web socket {e}")

