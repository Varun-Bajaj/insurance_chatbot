from fastapi import APIRouter
from .endpoints.auth_apis import auth_router
from .endpoints.chatbot_api import bot_router
from .endpoints.websockets import websocket_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(bot_router)
router.include_router(websocket_router)

