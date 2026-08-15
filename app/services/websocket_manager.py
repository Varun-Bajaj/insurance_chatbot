import typing
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
import asyncio

class WebSocketManager(object):
    """
    Base class for handling all websocket connections
    """
    _instance = None
    active_connections: typing.Dict[str, WebSocket] = {}

    def __new__(cls, *args, **kwargs):
        """
        creates a singleton class for socket manager class
        makes sure only one instance of the class exist in the lifecycle
        of the project
        :param args:
        :param kwargs:
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    async def connect(self, connection_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[str(connection_id)] = websocket

    async def disconnect_connection_web_socket_with_status_code(self, connection_id:str, status_code:int, reason:str):
        if connection_id in self.active_connections.keys():
            wb: WebSocket = self.active_connections[connection_id]
            await wb.close(code=status_code, reason=reason)
            del self.active_connections[connection_id]

    async def disconnect(self, connection_id: str):
        if connection_id in self.active_connections.keys():
            wb: WebSocket = self.active_connections[connection_id]
            await wb.close()
            del self.active_connections[connection_id]

    async def send(self, connection_id: str, message: dict):
        # print(f"sending: {message} to {connection_id}, {list(self.active_connections.keys())}")
        if connection_id in self.active_connections.keys():
            # if self.active_connections[connection_id]:
            websocket: WebSocket = self.active_connections[connection_id]
            # text_message = json.dumps(message)
            if websocket and websocket.application_state == WebSocketState.CONNECTED:
                message["ws_id"] = connection_id
                await websocket.send_json(message)

    async def broadcast(self, message: dict, connection_ids: typing.List[str] = None):
        """
        broadcast message, additionally provide list of connections ids for filter out
            the connections
        :param message:
        :param connection_ids:
        :return:
        """
        wbs: typing.List[WebSocket] = [
            self.active_connections[wb] for wb in connection_ids
        ] if connection_ids is not None else self.active_connections.values()

        for wb in wbs:
            await wb.send(message)


websocket_manager = WebSocketManager()
