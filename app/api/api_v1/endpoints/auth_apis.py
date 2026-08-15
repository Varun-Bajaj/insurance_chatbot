import subprocess
from fastapi import Request, Body, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi import FastAPI, Depends, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from utilities import *
from api.deps import get_db
# from services.auth_manager import Manager
from logs.logger_setup import setup_logger
from dao.chatbot_dao import *
from dao.auth_dao import *
from utilities.auth_utils import *
import uuid
from settings.setting import *

auth_router = APIRouter(
    prefix = '/auth',
    tags = ["Auth"],
)

# manager = Manager()
api_logger = setup_logger("api_logger")
templates = Jinja2Templates(directory="./templates")

# root method to be informed like server is started or ping
@auth_router.get("/", response_class=HTMLResponse)
async def api_read_root(request: Request):
    return templates.TemplateResponse(
        context={"request": request}, name="homepage.html"
    )


@auth_router.post("/login")
def login_user(request: Request, response: Response, credential = Body(None), db: Session = Depends(get_db)):
    """
    :param credential:
    :param db:
    :param request:
    :param response:
    :return:
    """
    user_id = credential.get("user_id")
    password = credential.get("password")
    client_id = credential.get("client_id")
    api_logger.info(f"Inside login user - {user_id} {password} {client_id}")
    jwt_token = login_user_token(user_id=user_id, password=password, client_id = client_id, db=db)
    if jwt_token is None:
        return {
            "status": "failure",
            "data": "invalid username or password"
        }
    status = save_token(jwt_token,client_id,user_id,db)
    if status:
        response.set_cookie("jwtToken", jwt_token)
        return {"access_token": jwt_token, "token_type": "bearer"}
    else:
        print(f"Token not stored in db")
        return {
            "status": "failure",
            "data": "invalid username or password"
        }

# API endpoint to generate session ID
@auth_router.post("/generate-session")
async def generate_session(request: Request, response: Response, token: str, patient_id: str, db: Session = Depends(get_db)):
    # Decode and verify the JWT token
    status, data = validate_jwt_token(token, db=db)
    if status:
        # Generate session ID using patient ID and a random UUID (or any other method)
        session_id = str(uuid.uuid4())  # Session ID is unique for each request
        return True , {"session_id": session_id, "patient_id": patient_id}

    # You can add additional checks here for the JWT payload if needed
    # For example, check if patient_id in the payload matches the patient_id in input
    # You can store session ID mapping to patient_id in a database if needed
    api_logger.warning(f"Token:{token} is invalid")
    return status, None


@auth_router.get("/login_page")
def get_login_page(request: Request, response: Response):
    """
    :param request:
    :param response:
    :return:
    """
    return templates.TemplateResponse(
        context={"request": request}, name="login.html"
    )

@auth_router.get("/restart_server")
async def restart_server(request: Request, is_data_ingestion_required: bool, is_prompt_change: bool,
                         changed_prompt: str, db: Session = Depends(get_db)):
    """
    Restarts the server with optional data ingestion and prompt change.

    Args:
        request (Request): HTTP request object.
        is_data_ingestion_required (bool): Flag to indicate if data ingestion is needed.
        is_prompt_change (bool): Flag to indicate if the chatbot prompt needs updating.
        changed_prompt (str): New prompt text if prompt change is required.
        db (Session): Database session dependency.

    Returns:
        Response: Server restart confirmation.
    """
    try:
        try:
            data = validate_token_from_headers(request, db=db)
        except HTTPException as e:
            raise e
        if is_data_ingestion_required:
            server_process = subprocess.Popen([ENV_PATH_IN_POC_GPU, 'ingest.py'])
        elif is_prompt_change and changed_prompt:
            SYSTEM_PROMPT = changed_prompt
        else:
            return {"status": "No need to restart the server!!!"}
        restart_service()
    except Exception as e:
        api_logger.exception(f"Exception in restart_server {str(e)}")


@auth_router.get("/logout")
async def api_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login_page", status_code=302)


@auth_router.get("/bot/home", description="gets home page data, q/a for users")
def get_home_page_data(request: Request, response: Response, db: Session = Depends(get_db)):
    user_id = request.state.user_info.get("sub", None)
    return get_qa_ans(user_id=user_id, db=db)

