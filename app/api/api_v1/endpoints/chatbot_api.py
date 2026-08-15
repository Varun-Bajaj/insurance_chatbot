from fastapi import Request, Body, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi import FastAPI, Depends, APIRouter
from fastapi.responses import JSONResponse
from settings.setting import *
from core.error_handler import create_error_dict, create_response
from logs.logger_setup import setup_logger
import asyncio
from fastapi.templating import Jinja2Templates
from utilities.auth_utils import *
from api.deps import get_db
from dao.chatbot_dao import *
from services.ingest import VectorDB_Ingestion
from services.query_handler import *
from utilities.make_json_files import BuildJson

bot_router = APIRouter(
    prefix = '/api',
    tags = ["Chatbot"],
)


api_logger = setup_logger("api_logger")
manager = Manager()
templates = Jinja2Templates(directory="./templates")

@bot_router.post("/register_client")
def register_client(client_id: str = Body(...), client_name: str = Body(...), db: Session = Depends(get_db)):
    """
    Registers a new client in the system.

    Args:
        client_id (str): Unique identifier for the client (provided in the request body).
        client_name (str): Name of the client (provided in the request body).
        db (Session): Database session dependency for performing database operations.

    Returns:
        Response: Confirmation of client registration or an error message.
    """
    status, code = manager.register_client_(client_id, client_name, db=db)
    if status:
        return {"message": "Client registered successfully"}
    return create_response(additional_info=create_error_dict(code))

@bot_router.get("/ping", tags=["readiness"])
def ping():
    """
    Ping to check is server live
    :return: dict
    """
    return {"result": "ok"}

@bot_router.post("/generate_token")
def generate_token(user_id: str = Body(...), password: str = Body(...), client_id: str = Body(...),
                   db: Session = Depends(get_db)):
    """
        Generates an authentication token for a user.

        Args:
            user_id (str): Unique identifier for the user.
            password (str): User's password for authentication.
            client_id (str): Client ID associated with the request.
            db (Session): Database session dependency.

        Returns:
            Response: Access token if authentication is successful, else an error message.
        """
    try:
        token_status, code = manager.get_token(user_id, password, client_id, db=db)
        if token_status:
            return {"status": "success", "access_token": code,
                    "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES, "token_type": "bearer", "resp_code": 200}
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED,
                            content=create_response(additional_info=create_error_dict(code)))
    except Exception as e:
        api_logger.exception(f"Exception in generate_token - {e}")
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED,
                            content=create_response(additional_info=create_error_dict(103)))

@bot_router.post("/document_ingestion")
async def document_ingestion():
    """
    Ingest the documents in the vectorDB

    Returns:
        string:- successfully documents ingested in the vectorDB
    """
    build_json_files = BuildJson()

    ## Make the json file of the table column details
    build_json_files.make_json_of_fetch_columns_table_wise()

    ## Make the json file of the graph info
    build_json_files.make_json_of_relationship_between_two_tables()

    ## Make the json file of the database schema info
    build_json_files.make_json_of_database_schema_info()

    ## VectorDB ingestion
    documents_ingest = VectorDB_Ingestion()
    status = await documents_ingest.Documents_ingestion()

    if status:
        return "Successfully documents ingested in the VectorDB"

    else:
        return "Documents is not ingested in the VectorDB"

@bot_router.post("/apis_ingestion")
async def apis_ingestion():
    """
    Ingest the APIS description, endpoints, and name in the VectorDB

    Returns:
        string:- print whether the ingested successfully ingested or not.
    """
    apis_ingest = VectorDB_Ingestion()
    status = await apis_ingest.APIS_ingestion()

    if status:
        return "Successfully APIs ingested in the VectorDB"

    else:
        return "APIS is not ingested in the VectorDB"


@bot_router.post("/faqs_ingestion")
async def faqs_ingestion():
    """
    Ingest the FAQS in the VectorDB

    Returns:
        string:- Successfully FAQS ingested in the VectorDB
    """

    faqs_ingest = VectorDB_Ingestion()
    status = await faqs_ingest.FAQS_ingestion()

    if status:
        return "Successfully faqs ingested in the VectorDB"

    else:
        return "FAQS is not ingested in the VectorDB"

@bot_router.post("/langgraph_show")
async def show_langgraph_flow():
    from utilities.langgraph_flow import show

    await show()

@bot_router.post("/register_user")
def register_user(user_id: str = Body(...), user_name: str = Body(...), password: str = Body(...),
                  db: Session = Depends(get_db)):
    """
    Registers a new user in the system.

    Args:
        user_id (str): Unique identifier for the user.
        user_name (str): Name of the user.
        password (str): User's password (should be stored securely).
        db (Session): Database session dependency.

    Returns:
        Response: Confirmation of user registration or an error message.
    """
    status, code = manager.register_user_(user_id, user_name, password, db=db)
    if status:
        return create_response(additional_info=code)
    return create_response(additional_info=create_error_dict(code))


@bot_router.post("/access_user")
def access_user(user_id: str = Body(...), client_id: str = Body(...), db: Session = Depends(get_db)):
    """
    Grants access to a user based on their credentials and client association.

    Args:
        user_id (str): Unique identifier for the user.
        client_id (str): Associated client ID.
        db (Session): Database session dependency.

    Returns:
        Response: Access confirmation or error message.
    """
    status, code = manager.give_user_access(user_id, client_id, db=db)
    if status:
        return {"message": "successfully gave access to user."}
    return create_response(additional_info=create_error_dict(code))



def is_session_id_valid(session_id:str):
    if not session_id or len(session_id.strip()) == 0 or not session_id.isalnum():
        return False
    return True


@bot_router.post("/bot/query/save")
# def def_save_query(request: Request, response: Response,session_id:str = Body(...), query: str = Body(...), db: Session = Depends(get_db)):
def save_query(request: Request, session_id: str = Body(...), query: str = Body(...), db: Session = Depends(get_db)):
    """
    Saves a chatbot query for a given session.

    Args:
        request (Request): HTTP request object.
        session_id (str): Unique session identifier.
        query (str): User's query to be stored.
        db (Session): Database session dependency.

    Returns:
        Response: Confirmation of query storage.
    """
    try:
        try:
            credential = validate_token_from_headers(request, db=db)
        except HTTPException as e:
            raise e
        if not is_session_id_valid(session_id):
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": "Invalid session_id: must be a non-empty and contain only alphanumeric characters.",
            }
        # Check if query_id is missing or invalid
        if not query or not query.strip():
            return {
                "status_code": status.HTTP_400_BAD_REQUEST,
                "data": "Invalid query_id: must be a non-empty string.",
            }
        api_logger.info(f"saving query from user")
        # result = db.execute("SHOW TABLES;")
        # api_logger.info(f"results of tables {result}")
        analysis_obj = add_qa_user(user_id=credential[1], db=db, query=query)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "data": "Query saved",
                "query_id": analysis_obj.id
            }
        )
    except Exception as ex:
        api_logger.exception(f"Exception in api_save_query {ex}")
        raise ex


@bot_router.get("/bot/query/response")
async def get_response_from_chatbot(request: Request, session_id: str, query_id: int, db: Session = Depends(get_db)):
    """
        Retrieves the chatbot's response for a specific query.

        Args:
            request (Request): HTTP request object.
            session_id (str): Unique session identifier.
            query_id (int): Identifier for the stored query.
            db (Session): Database session dependency.

        Returns:
            Response: The chatbot's response to the query.
        """
    # available_model = None

    try:
        try:
            credential = validate_token_from_headers(request, db=db)
        except HTTPException as e:
            raise e
#        available_model = await get_free_model()
#        if not available_model:
#            return {
#                "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
#                "data": "service is not available due to limit of resources",
#                "query_id": query_id,
#                "query": None,
#                "response": None
#            }
#        global response_query_count
#        response_query_count += 1
#        app_logger.info(f"Total response query count {response_query_count}")
        ## Use below for multi-request
        if not API_BASED_QUERY_RESPONSE:
            # print("Now handle the query")
            asyncio.create_task(handle_query(credential[1], session_id, query_id, db))
            return {
                "status_code": status.HTTP_200_OK,
                "data": "Generating the response",
            }
        else:
            ## Use below for single-request
            print("Now handle the query")
            response = await handle_query(credential[1], session_id, query_id, db)
            if 'answer' in response and 'query' in response:
                return {
                    "status_code": status.HTTP_200_OK,
                    "data": "response generated",
                    "query_id": query_id,
                    "query": response['query'],
                    "response": response['answer']
                }
            else:
                return {
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "data": "Unable to generate response from server",
                    "query_id": query_id,
                    "query": None,
                    "response": None
                }
    except Exception as e:
        print(f"Exception in get_response_from_chatbot {e}\n\n")
        app_logger.exception(f"Exception in get_response_from_chatbot {e}")
        raise e
    finally:
       # if available_model and available_model.is_busy:
          # available_model.is_busy = False
       print("get_response_from_chatbot")
