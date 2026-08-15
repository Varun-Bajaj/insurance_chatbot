import subprocess
from datetime import datetime, timedelta
from fastapi import Request, Body, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.orm import Session
from services.auth_manager import Manager
from logs.logger_setup import setup_logger
from settings.setting import *

app_logger = setup_logger("app_logger")

manager = Manager()

def restart_service():
    try:
        # Restart the service using systemctl
        subprocess.run(["sudo", "systemctl", "restart", SERVICE_NAME], check=True)
        app_logger.info("Service restarted successfully.")
    except subprocess.CalledProcessError as ex:
        app_logger.exception(f"Failed to restart the service: {ex}")
    except Exception as ex:
        app_logger.exception(f"An error occurred: {ex}")

def validate_token_from_headers(request, db: Session):
    """
    Validates the given access token.

    Args:
        request: API Request object.
        db (Session): Database session dependency.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    auth_token = request.headers.get("Authorization")
    #auth_token = load_settings.auth_token
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token not present",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_token.split()[1]
    #access_token = auth_token
    return validate_token_from_arguments(access_token=access_token, db=db)

def validate_token_from_arguments(access_token, db:Session):
    """
    Validates the given access token.

    Args:
        access_token (str): Token provided for authentication.
        db (Session): Database session dependency.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    if access_token is None:
        access_token= auth_token
    print(f"Token is {access_token}")
    result, data = manager.validate_token(access_token, db=db)
    if result in [208]:
        raise Exception
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token expired or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return data
