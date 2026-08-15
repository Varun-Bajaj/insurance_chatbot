from qdrant_client import models, QdrantClient, AsyncQdrantClient
import json
import os
import base64
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.utilities import SQLDatabase
import mysql.connector
from urllib.parse import quote
import asyncio

# LOGS_PATH = os.path.join(os.getcwd(), "Chatbot_data/Chatbot_app_logs")
# FILES_PATH = "/home/dosepackai/billrMD/Data/json"
CONFIG_FILE_PATH = os.path.join(os.getcwd(), "config/config_env.json")
# CHROMADB_FILE_PATH = "/home/dosepackai/VectorDB_files/Chatbot_Text2Sql/chromadb"
GUARDRAILS_CONFIG_PATH = os.path.join(os.getcwd(), "config/huggingface")
GUARDRAILS_OLLAMA_CONFIG_PATH = os.path.join(os.getcwd(), "config/ollama")
GUARDRAILS_OLA_CONFIG_PATH = os.path.join(os.getcwd(), "config/krutrim_ola")

WEBSOCKET_CLOSE_CODES = {
    "NORMAL_CLOSURE": 1000, # Used for a graceful shutdown.
    "GOING_AWAY": 1001, # Client is closing, e.g., page reload.
    "PROTOCOL_ERROR": 1002, # WebSocket protocol violation detected.
    "UNSUPPORTED_DATA": 1003, # Received invalid or unexpected data type.
    "ABNORMAL_CLOSURE" : 1006, # Indicates a failure (e.g., network issue).
    "INVALID_TOKEN": 1008, # Message violates server policies.
    "INVALID_SESSION": 1003, # Received invalid SESSION ID
    "TRY_AGAIN_LATER": 1013, # Temporary condition (e.g., rate limiting).
}

# Load env file
with open(CONFIG_FILE_PATH) as env_file:
    env_data = json.load(env_file)

## load the dpws database configuration
password = env_data["DPWS_DATABASE"]['db_password']
decoded_bytes = base64.b64decode(password)
DPWS_DB_PASS = decoded_bytes.decode('utf-8')
DPWS_DB_USERNAME = env_data["DPWS_DATABASE"]['db_username']
DPWS_DB_HOST = env_data["DPWS_DATABASE"]['db_host']
DPWS_DB_PORT = env_data["DPWS_DATABASE"]['db_port']
DPWS_DB_NAME = env_data["DPWS_DATABASE"]['db_name']

## load the DosepacksupportChatbot configuration
db_user = str(os.environ.get("db_user", "root"))
db_pass = str(os.environ.get("db_pass", "12345678"))
db_name = str(os.environ.get("db_name", "SupportChatbot"))
db_url = str(os.environ.get("db_url", "0.0.0.0"))

ROOT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
EMBEDDING_MODEL = env_data['embedding_model']
RERANKER_MODEL = env_data['reranker_model']

## Load the configuration of the ollama coder model from env file
OLLAMA_MAIN_MODEL = env_data["OLLAMA"]['main_model']
OLLAMA_BASE_URL = env_data["OLLAMA"]['base_url']
OLLAMA_TEMPERATURE = env_data["OLLAMA"]['temperature']
OLLAMA_NUM_CTX = env_data["OLLAMA"]['num_ctx']

KRUTRIM_INSTRUCTION_MODEL = env_data["KRUTRIM"]['instruction_model']
KRUTRIM_INSTRUCTION_BASE_URL = env_data["KRUTRIM"]['instruction_base_url']
KRUTRIM_INSTRUCTION_TEMPERATURE = env_data["KRUTRIM"]['instruction_temperature']
KRUTRIM_INSTRUCTION_NUM_CTX = env_data["KRUTRIM"]['instruction_num_ctx']
KRUTRIM_INSTRUCTION_API_KEY = env_data["KRUTRIM"]['instruction_api_key']

## Load the configuaration of the krutrim ola model from env file
KRUTRIM_MODEL = env_data["KRUTRIM"]['main_model']
KRUTRIM_BASE_URL = env_data["KRUTRIM"]['base_url']
KRUTRIM_TEMPERATURE = env_data["KRUTRIM"]['temperature']
KRUTRIM_NUM_CTX = env_data["KRUTRIM"]['num_ctx']
KRUTRIMAI_API_KEY = env_data["KRUTRIM"]['api_key']

## load the configuration of the ollama text model for the greeting handle from env file
GREETINGS_MAIN_MODEL = env_data["GREETINGS"]['main_model']
GREETINGS_BASE_URL = env_data["GREETINGS"]['base_url']
GREETINGS_TEMPERATURE = env_data["GREETINGS"]['temperature']
GREETINGS_NUM_CTX = env_data["GREETINGS"]['num_ctx']


FLAG_OLLAMA_CONFIG = env_data['flag_ollama_config']
HF_TOKEN = env_data['huggingface_token']
FLAG_STORE_QUERY = env_data['flag_store_query']
VECTOR_DB = env_data['vector_db']
MODEL = env_data['MODEL']
APPROACH = env_data["APPROACH"]

## Connect with the mysql dpws database
cnx = mysql.connector.connect(
    host=DPWS_DB_HOST,
    user=DPWS_DB_USERNAME,
    password=DPWS_DB_PASS,
    database=DPWS_DB_NAME
)

DB = cnx.cursor(dictionary=True)

## load the file path of the json file and excel file
DATABASE_SCHEMA_INFO_FILE_PATH = os.path.join(os.getcwd(), "data/careloop_database_schema_info.json")
TABLE_COLUMN_DETAILS = os.path.join(os.getcwd(), "data/careloop_table_column_details.json")
GRAPH_INFO_PATH = os.path.join(os.getcwd(), "data/careloop_graph_info.json")
EXCEL_FILE_PATH = "/root/Database_Sheet_Sheet1.xlsx"

with open(f'{DATABASE_SCHEMA_INFO_FILE_PATH}', 'r') as f:        # 2. open in read mode with context management :contentReference[oaicite:4]{index=4}
    SCHEMA_DICT = json.load(f)[0]

with open(f'{TABLE_COLUMN_DETAILS}', 'r') as f:
    TC_DETAILS = json.load(f)

with open(f'{GRAPH_INFO_PATH}', 'r') as f:
    GRAPH_INFO = json.load(f)[0]

## Load the prompts
if APPROACH == 1:
    PROMPT_FILES = {
        "CONTEXTUALIZE_Q_PROMPT": os.path.join(os.getcwd(), "prompts/contextualize_q_prompt.txt"),
        "SYSTEM_PROMPT": os.path.join(os.getcwd(), "prompts/Approach_1_prompts/system_prompt.txt"),
        "QUERY_CHECKER_PROMPT": os.path.join(os.getcwd(), "prompts/Approach_1_prompts/query_checker_prompt.txt"),
        "REGENERATE_QUERY_PROMPT": os.path.join(os.getcwd(), "prompts/Approach_1_prompts/regenerate_query_prompt.txt"),
        "DECISION_SQLQUERY_OR_API_PROMPT": os.path.join(os.getcwd(), "prompts/decision_sqlquery_or_api_prompt.txt"),
        "API_CORRECTION_PROMPT": os.path.join(os.getcwd(), "prompts/api_correction_prompt.txt"),
        "DECISION_SQLQUERY_EXECUTION_OR_APICALL_PROMPT": os.path.join(os.getcwd(), "prompts/decision_sqlquery_execution_or_apicall_prompt.txt"),
        "FIELD_EXTRACTION_PROMPT": os.path.join(os.getcwd(), "prompts/field_extraction_prompt.txt"), 
        "NAME_DETECTION_PROMPT": os.path.join(os.getcwd(), "prompts/name_detect_prompt.txt"),
    }

    PROMPTS = {
    key: open(os.path.join(ROOT_DIRECTORY, path), "r", encoding="utf-8").read()
    for key, path in PROMPT_FILES.items()
    }
    SYSTEM_PROMPT = ChatPromptTemplate.from_messages([
        ("system", PROMPTS["SYSTEM_PROMPT"]),
        ("human", "{user_query}"),
    ])

    QUERY_CHECKER_PROMPT = ChatPromptTemplate.from_messages([
        ("system", PROMPTS["QUERY_CHECKER_PROMPT"]),
        ("human", "{query}"),
    ])

    REGENERATE_QUERY_PROMPT = ChatPromptTemplate.from_messages([
        ("system", PROMPTS["REGENERATE_QUERY_PROMPT"]),
        ("human", "{user_query}"),
    ])

elif APPROACH == 2:
    PROMPT_FILES = {
        "CONTEXTUALIZE_Q_PROMPT": os.path.join(os.getcwd(), "prompts/contextualize_q_prompt.txt"),
        "SYSTEM_PROMPT": os.path.join(os.getcwd(), "prompts/Approach_2_prompts/system_prompt.txt"),
        "SYSTEM_PROMPT_2": os.path.join(os.getcwd(), "prompts/Approach_2_prompts/system_prompt_2.txt"),
        "TARGET_TABLE_FROM_SQL_PROMPT": os.path.join(os.getcwd(), "prompts/Approach_2_prompts/target_table_from_sql_prompt.txt"),
        "DECISION_SQLQUERY_OR_API_PROMPT": os.path.join(os.getcwd(), "prompts/decision_sqlquery_or_api_prompt.txt"),
        "API_CORRECTION_PROMPT": os.path.join(os.getcwd(), "prompts/api_correction_prompt.txt"),
        "DECISION_SQLQUERY_EXECUTION_OR_APICALL_PROMPT": os.path.join(os.getcwd(), "prompts/decision_sqlquery_execution_or_apicall_prompt.txt"),
        "FIELD_EXTRACTION_PROMPT": os.path.join(os.getcwd(), "prompts/FIELD_EXTRACTION_PROMPT.txt"),
        "NAME_DETECTION_PROMPT": os.path.join(os.getcwd(), "prompts/name_detect_prompt.txt"),
    }

    PROMPTS = {
        key: open(os.path.join(ROOT_DIRECTORY, path), "r").read()
        for key, path in PROMPT_FILES.items()
    }

    SYSTEM_PROMPT = ChatPromptTemplate.from_messages([
        ("system", PROMPTS["SYSTEM_PROMPT"]),
        ("human", "{user_query}"),
    ])

    SYSTEM_PROMPT_2 = ChatPromptTemplate.from_messages([
        ("system", PROMPTS["SYSTEM_PROMPT_2"]),
        ("human", "{user_query}"),
    ])

    TARGET_TABLE_FROM_SQL_PROMPT = ChatPromptTemplate.from_messages([
        ("system", PROMPTS["TARGET_TABLE_FROM_SQL_PROMPT"]),
        ("human", "{SQL_QUERY}")
    ])

CONTEXTUALIZE_Q_PROMPT = ChatPromptTemplate.from_messages([
    ("system", PROMPTS["CONTEXTUALIZE_Q_PROMPT"]),
    ("human", "{input}"),
])

NAME_DETECTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", PROMPTS["NAME_DETECTION_PROMPT"]),
    ("human", "query: {query}"),
])

DECISION_SQLQUERY_OR_API_PROMPT = ChatPromptTemplate.from_messages([
    ("system", PROMPTS["DECISION_SQLQUERY_OR_API_PROMPT"]),
    ("human", "{user_query}"),
])

FIELD_EXTRACTION_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", PROMPTS["FIELD_EXTRACTION_PROMPT"]),
    ("human", "{user_query}\n{api_response}"),
])

API_CORRECTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", PROMPTS["API_CORRECTION_PROMPT"]),
    ("human", "{user_query}"),
])

DECISION_SQLQUERY_EXECUTION_OR_APICALL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", PROMPTS["DECISION_SQLQUERY_EXECUTION_OR_APICALL_PROMPT"]),
    ("human", "{user_query}"),
])

## initialize the jwt token key
JWT_TOKEN_KEY = "GYQA-KzHbh_6BrYITGzYO4DPbcnJ6s2KNBA1PSVNqdg"

## Initialize the vector db root path
CHROMADB_VECTOR_DB_ROOT = os.path.join(os.getcwd(), f"VectorDB_files/CHROMADB/{DPWS_DB_NAME}")
QDRANT_VECTOR_DB_ROOT = os.path.join(os.getcwd(), f"VectorDB_files/QDRANTDB/{DPWS_DB_NAME}")

## Initialize the vector db configuaration like collection and client
if VECTOR_DB == 1:
    CHROMADB_FILE_PATH = f"{CHROMADB_VECTOR_DB_ROOT}/schema"
    CHROMADB_COLLECTION_NAME = "SQL_Schema_Collection"
    FAQS_CHROMADB_FILE_PATH = f"{CHROMADB_VECTOR_DB_ROOT}/faqs"
    FAQS_CHROMADB_COLLECTION_NAME = "FAQS_Schema_Collection"
    APIS_CHROMADB_FILE_PATH = f"{CHROMADB_VECTOR_DB_ROOT}/apis"
    APIS_CHROMADB_COLLECTION_NAME = "APIS_Collection"

elif VECTOR_DB == 2:
    ## SCHEMA QDRANT
    QDRANT_COLLECTION_NAME = "SQL_Schema_VectorDB"
    QDRANT_PATH = f"{QDRANT_VECTOR_DB_ROOT}/schema"
    QDRANT_CLIENT = AsyncQdrantClient(path=QDRANT_PATH)

    ## FAQS QDRANT
    FAQS_QDRANT_COLLECTION_NAME = "FAQS_Schema_VectorDB"
    FAQS_QDRANT_PATH = f"{QDRANT_VECTOR_DB_ROOT}/faqs"
    FAQS_QDRANT_CLIENT = AsyncQdrantClient(path=FAQS_QDRANT_PATH)

    ## APIS QDRANT
    APIS_QDRANT_COLLECTION_NAME = "APIS_VectorDB"
    APIS_QDRANT_PATH = f"{QDRANT_VECTOR_DB_ROOT}/apis"
    APIS_QDRANT_CLIENT = AsyncQdrantClient(path=APIS_QDRANT_PATH)


## Load the langsmith configuration and the HF token
os.environ["LANGSMITH_TRACING"] = env_data['langsmith_tracing']
os.environ["LANGSMITH_ENDPOINT"] = env_data['langsmith_endpoint']
os.environ["LANGSMITH_API_KEY"] = env_data['langsmith_api_key']
os.environ["LANGSMITH_PROJECT"] = env_data['langsmith_project']
os.environ['HUGGINGFACE_TOKEN'] = HF_TOKEN

## For chatbot
DATABASE_URL = "sqlite:///./test.db"
## For Conversation storage
SYNC_DB_URL = "sqlite:///memory.db"
# SYNC_DB_URL = "sqlite+aiosqlite:///memory.db"

auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbGllbnRfaWQiOiIxIiwidXNlcl9pZCI6IjEiLCJleHAiOjE5MDI5MTkwOTl9.3vFc7ux6_4H-E_bzInaLgbgs9RRd-XC2vHE3LMZu71U"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440 * 30  # 1 day
PASSWORD_SECRET = "DosepackAI"

LOGS_PATH = os.path.join(os.getcwd(), "app_data", "app_logs/logs")
FILES_PATH = os.path.join(os.getcwd(), "app_data/files")
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

CONFIG_FILE_PATH = os.path.join(ROOT_DIRECTORY,"app_data/config_env.json")
ENV_PATH_IN_POC_GPU = "/root/miniconda3/envs/careloop/bin/python"
# ENV_PATH_IN_MEDITAB_GPU = "/home/dosepack/miniforge3/envs/guardrails/bin/python"
COPY_INGEST_DATA = True

SERVICE_NAME = "chatbot.service"

NUMBER_OF_MODEL_PIPELINE = env_data["NUMBER_OF_MODEL_PIPELINE"]
MAX_NUMBER_OF_PIPELINES = env_data["MAX_NUMBER_OF_PIPELINES"]
API_BASED_QUERY_RESPONSE = env_data["API_BASED_QUERY_RESPONSE"]
SOURCE_DIRECTORY_LOCATION = env_data["SOURCE_DIRECTORY_LOCATION"]

SERVER_IP_ADDRESS = env_data["SERVER_IP_ADDRESS"]
SERVER_PORT_ADDRESS = env_data["SERVER_PORT_ADDRESS"]

## Load the faqs retriever thresold
FAQS_THRESHOLD = env_data["FAQS_THRESHOLD"]
FAQS_CHROMADB_DISTANCE = env_data["FAQS_CHROMADB_DISTANCE"]

## load the api retriever thresold
API_THRESHOLD = env_data["API_THRESHOLD"]
API_CHROMADB_DISTANCE = env_data["API_CHROMADB_DISTANCE"]

## Load the how many conversation history maintain its count
MAINTAIN_CONVERSATION_HISTORY_COUNT = env_data["MAINTAIN_CONVERSATION_HISTORY_COUNT"]

## Load the CRM configuration
CRM_IP_ADDRESS = env_data['CRM_IP_ADDRESS']
CRM_PORT = env_data['CRM_PORT']

# OLLAMA_INSTRUCTION_MODEL = env_data["OLLAMA"].get("instruction_model", "llama3.3-70b-instruct")
# OLLAMA_INSTRUCTION_BASE_URL = env_data["OLLAMA"].get("instruction_base_url", "http://localhost:11420")
# OLLAMA_INSTRUCTION_TEMPERATURE = env_data["OLLAMA"].get("instruction_temperature", 0.6)
# OLLAMA_INSTRUCTION_NUM_CTX = env_data["OLLAMA"].get("instruction_num_ctx", 512)
# OLLAMA_INSTRUCTION_API_KEY = env_data["OLLAMA"]['instruction_api_key']