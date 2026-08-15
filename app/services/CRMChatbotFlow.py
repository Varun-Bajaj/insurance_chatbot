import ast

from langchain_ollama.llms import OllamaLLM
from langchain_ollama import ChatOllama
from sympy import EX
from langchain_openai import ChatOpenAI
from langsmith import traceable
from urllib.parse import urlparse, parse_qs, urlencode
from utilities.VectorDB import emb_fn
from qdrant_client import models, QdrantClient, AsyncQdrantClient
import chromadb
from settings.setting import *
from chromadb.config import Settings
from typing import TypedDict, Sequence
from langchain.schema.messages import HumanMessage as HM, AIMessage as AM, SystemMessage as SM
from langchain_core.messages import HumanMessage
from langchain_core.messages.ai import AIMessage
from langgraph.graph import StateGraph, END
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
import re
import time
from logs.logger_setup import setup_logger
from dao.chatbot_dao import *
from services.websocket_manager import websocket_manager
from typing import List
# import sqlvalidator
from mysql.connector import OperationalError
from services.get_bot_history import get_session_history_with_sql_chat_history
import requests

class AgentState(TypedDict, total=False):
    user_query: str
    session_id: str
    query_id: str
    apis_details: List[str]
    messages: Sequence[SM | HM | AM]
    sql_query: str = None
    get_important_tables: bool = True
    tables_info: str
    faqs_content: List[str]

logger = setup_logger("Normal_Agent_chatbot_answer")
schema_logger = setup_logger("Normal_Agent_retriever_tables_schema")
timer = setup_logger("Normal_Agent_timer")

class CRMChatbotManager:
    def __init__(self):
        if MODEL == 1:
            self.llm = ChatOllama(model=OLLAMA_MAIN_MODEL, base_url=OLLAMA_BASE_URL, temperature=OLLAMA_TEMPERATURE,
                                  num_ctx=OLLAMA_NUM_CTX, cache=False)

        elif MODEL == 2:
            self.llm = ChatOpenAI(api_key=KRUTRIMAI_API_KEY, base_url=KRUTRIM_BASE_URL, model=KRUTRIM_MODEL,
                                  temperature=KRUTRIM_TEMPERATURE)
            
            self.instructions_llm = ChatOpenAI(api_key=KRUTRIM_INSTRUCTION_API_KEY, base_url=KRUTRIM_INSTRUCTION_BASE_URL,
                                               model=KRUTRIM_INSTRUCTION_MODEL, temperature=KRUTRIM_INSTRUCTION_TEMPERATURE)

        # self.rewrite_llm = ChatOllama(model="llama3.2:3b-instruct-q4_0", base_url="http://localhost:11421", temperature=0.05)

        if VECTOR_DB == 1:
            self.client = chromadb.PersistentClient(path=CHROMADB_FILE_PATH)
            self.pooled_collection = self.client.get_or_create_collection(name=CHROMADB_COLLECTION_NAME,
                                                                          embedding_function=emb_fn())

            self.faqs_client = chromadb.PersistentClient(path=FAQS_CHROMADB_FILE_PATH)
            self.faqs_pooled_collection = self.faqs_client.get_or_create_collection(
                name=FAQS_CHROMADB_COLLECTION_NAME,
                embedding_function=emb_fn())

            self.apis_client = chromadb.PersistentClient(path=APIS_CHROMADB_FILE_PATH)
            self.apis_pooled_collection = self.apis_client.get_or_create_collection(
                name=APIS_CHROMADB_COLLECTION_NAME,
                embedding_function=emb_fn()
            )

        elif VECTOR_DB == 2:
            self.qdrant_client = QDRANT_CLIENT
            self.embedding_model = emb_fn().embedding_model

            self.faqs_qdrant_client = FAQS_QDRANT_CLIENT

            self.apis_qdrant_client = APIS_QDRANT_CLIENT

        self.conversation_history = {}
        self.last_name = []

    def extract_query(self, markdown_text):
        pattern_1 = r"```sql\s*(.*?)\s*```"
        match_1 = re.search(pattern_1, markdown_text, re.DOTALL | re.IGNORECASE)
        pattern_2 = r"(SELECT[\s\S]*?;)"
        match_2 = re.search(pattern_2, markdown_text, re.IGNORECASE)

        if match_1:
            extracted_query = match_1.group(1).strip()
            print(f"Extracted SQL Query by match 1: {extracted_query}")
            return extracted_query

        elif match_2:
            extracted_query = match_2.group(1).strip()
            print(f"Extracted SQL Query by match 2: {extracted_query}")
            return extracted_query

        else:
            return markdown_text.strip()

    async def get_faqs_content_tables(self, user_query):
        try:
            if VECTOR_DB == 1:
                faqs = await self.faqs_pooled_collection.query(
                    query_texts=[user_query],
                    n_results=5
                )

                # print("=====================FAQS=======================")
                # print(f"\n\n{faqs}\n\n")
                # print("================================================")

                faqs_score = faqs['distances'][0]
                faqs_vector_content = faqs['documents'][0]
                faqs_vector_tables = faqs['metadatas'][0]
                print(faqs_score)

                faqs_content = []
                faqs_tables = []

                for i, score in enumerate(faqs_score):
                    print(f"The get_faqs_content_tables: {i} and {score}")
                    if score <= FAQS_CHROMADB_DISTANCE:
                        faqs_merge_content_tables = f"User_Query: {faqs_vector_content[i]}\n SQL_Query: {faqs_vector_tables[i]['sql_query']}"
                        faqs_content.append(faqs_merge_content_tables)
                        faqs_tables.extend(ast.literal_eval(faqs_vector_tables[i]['table_info']))

                return faqs_content, faqs_tables

            elif VECTOR_DB == 2:
                response = await self.faqs_qdrant_client.query_points(
                    collection_name=FAQS_QDRANT_COLLECTION_NAME,
                    query=self.embedding_model.encode(user_query).tolist(),
                    limit=5,
                    score_threshold=FAQS_THRESHOLD
                )

                hits = response.points

                faqs_content = []
                faqs_tables = []

                print("=============================================")

                for hit in hits:
                    payload = hit.payload
                    print(f"\n\nUser Query: {payload['user_query']}\n\n")
                    print(f"\n\n Score: {hit.score}\n\n")
                    content = f"User_Query: {payload['user_query']}\n SQL_Query: {payload['sql_query']}"
                    faqs_content.append(content)
                    faqs_tables.extend(payload['content'])

                print("============================================")

                return faqs_content, faqs_tables

            return [], []

        except Exception as e:
            logger.exception(f"Exception has been occurred in retrieve faqs: {e}\n")
            print(f"Exception has been occurred during retrieve faqs: {e}\n\n")
            return [], []    

    async def get_apis_details(self, user_query):
        try:
            if VECTOR_DB == 1:
                apis = await self.apis_pooled_collection.query(
                    query_texts=[user_query],
                    n_results=5
                )
                

                print("=====================APIS=======================")
                print(f"\n\napis:{apis}\n\n")
                print("================================================")

                apis_score = apis['distances'][0]
                apis_vector_description = apis['documents'][0]
                apis_vector_name_endpoint = apis['metadatas'][0]

                # Defensive: get the minimum length to avoid index errors
                min_len = min(len(apis_score), len(apis_vector_name_endpoint))

                apis_details = []

                for i in range(min_len):
                    score = apis_score[i]
                    print(f"The get_faqs_content_tables: {i} and {score}")
                    if score <= API_CHROMADB_DISTANCE:
                        api_detail = (
                            f"API_Name: {apis_vector_name_endpoint[i]['Name']}\n"
                            f"API_Endpoint: {apis_vector_name_endpoint[i]['Endpoint']}\n"
                            f"API_Description: {apis_vector_name_endpoint[i]['Description']}\n"
                            f"API_Required_Fields: {apis_vector_name_endpoint[i].get('Required fields', 'N/A')}"
                        )
                        apis_details.append(api_detail)

                return apis_details

            elif VECTOR_DB == 2:
                response = await self.apis_qdrant_client.query_points(
                    collection_name=APIS_QDRANT_COLLECTION_NAME,
                    query=self.embedding_model.encode(user_query).tolist(),
                    limit=5,
                    # score_threshold=API_THRESHOLD
                )

                hits = response.points

                apis_details = []

                print("=============================================")

                for hit in hits:
                    payload = hit.payload
                    print(f"\nAPI Name: {payload['Name']}\n")
                    print(f"Score: {hit.score}\n")
                    print(f"Endpoint: {payload['Endpoint']}\n")
                    print(f"Description: {payload['Description']}\n\n")
                    print(f"Required fields: {payload['Required fields']}\n\n")
                    print(f"Page_Content: {payload['Page_content']}\n\n")
                    print("======================================")
                    content = f"API_Name: {payload['Name']}\n API_Endpoint: {payload['Endpoint']}\n API_Description: {payload['Description']}\n API_Required_Fields: {payload.get('Required fields', 'N/A')}"
                    apis_details.append(content)

                print("============================================")

                return apis_details

            return None
    
        except Exception as e:
            logger.exception(f"Exception has been occurred in retrieve apis: {e}\n")
            print(f"Exception has been occurred during retrieve apis: {e}\n\n")
            return []

    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = ChatMessageHistory()
            print("New session created.")

        else:
            print("Existing session retrieved.")

        print(f"session history: {self.conversation_history[session_id]}")
        return self.conversation_history[session_id]

    def store_message(self, session_id: str, user_message: str, ai_response: str):
        try:
            history = get_session_history_with_sql_chat_history(session_id)

            # Add user and AI messages to history
            history.add_user_message(user_message)
            history.add_ai_message(ai_response)

            logger.info(f"Stored User Message: {user_message}\n")
            logger.info(f"Stored AI Response: {ai_response}\n")

            print(f"Stored User Message: {user_message}")
            print(f"Stored AI Response: {ai_response}")

            return True

        except Exception as e:
            logger.exception(e)
            raise e

    # def store_message_in_crm_api(self, session_id:str, user_message: str, ai_response: str):
    #     try:
    #         history = get_session_history_with_crm_api_chat_history(session_id=session_id)

    #         # Add user and AI messages to history
    #         history.add_user_message(user_message)
    #         history.add_ai_message(ai_response)

    #         logger.info(f"Stored User Message: {user_message}\n")
    #         logger.info(f"Stored AI Response: {ai_response}\n")

    #         print(f"Stored User Message: {user_message}")
    #         print(f"Stored AI Response: {ai_response}")

    #         return True

    #     except Exception as e:
    #         logger.exception(e)
    #         raise e

    async def get_tables_schema(self, user_query):
        try:
            if VECTOR_DB == 1:
                tables_list = []
                imp_tables = await self.pooled_collection.query(
                    query_texts=[user_query],
                    n_results=10,
                    ## from vectordb i am extracting the top 10 similar table and found the schema of those tables.
                )

                tables = imp_tables['documents'][0]

                for i in tables:
                    tables_list.append(i)

                return tables_list

            elif VECTOR_DB == 2:
                tables_list = []
                response = await self.qdrant_client.query_points(
                    collection_name=QDRANT_COLLECTION_NAME,
                    query=self.embedding_model.encode(user_query).tolist(),
                    limit=20,
                    score_threshold=0.60,
                )

                hits = response.points

                for hit in hits:
                    di = hit.payload
                    tables_list.append(di['Content'])

                return tables_list

            return []

        except Exception as e:
            print(f"Exception has been occurred in the get tables schema function is: {e}\n")
            logger.exception(f"Exception has been occurred in the get tables schema function is: {e}\n")
            return []

    async def main_decide_sqlquery_or_api(self, user_query, tables_schema, apis_details, faqs_content):
        start_time = time.time()

        chain = DECISION_SQLQUERY_OR_API_PROMPT | self.llm
        print("inside the main_decide_sqlquery_or_api function")
        reply = await chain.ainvoke(
            {"user_query": user_query, "table_info": tables_schema, "api_details": apis_details, "faqs": faqs_content}
        )

        print("=========================================================================")
        print(f"\nDecision of sql query(0) or api(1): {reply.content}\n")
        print("=========================================================================")

        logger.info(f"\n Decision of sql query or api: {reply.content}\n")
        end_time = time.time()

        timer.info(f"Time taken by the decision whether go to the sql query generation or api: {end_time - start_time}")
        return reply.content

    # async def main_decide_sqlquery_execute_or_apicall(self, user_query, apis_details):
    #     start_time = time.time()

    #     chain = DECISION_SQLQUERY_EXECUTION_OR_APICALL_PROMPT | self.llm

    #     result = await chain.ainvoke({"user_query": user_query, "apis_details": apis_details})

    #     print("============================================================")
    #     print(f"\nDecision whether to execute(1) sql query or api call(0): {result.content}\n")
    #     logger.info(f"Decision whether to execute(1) sql query or api call(0): {result.content}")
    #     print("============================================================")

    #     end_time = time.time()

    #     timer.info(f"Time is required to decision sql query execution or api call: {end_time - start_time}")

    #     return result.content

    async def main_api_correction(self, user_query, apis_details, state):
        start_time = time.time()
        
        chain = API_CORRECTION_PROMPT | self.llm
        print("inside the main_api_correction function")
        history = get_session_history_with_sql_chat_history(state['session_id'])
        chat_history = []

        for message in history.messages:
            if isinstance(message, HumanMessage):
                chat_history.append(f"Human: {message.content}")

            elif isinstance(message, AIMessage):
                chat_history.append(f"AI: {message.content}")
        
        reply = await chain.ainvoke(
            {"user_query": user_query, "apis_details": apis_details, "chat_history": chat_history}
        )
        
        print("======================================================================")
        print(f"\nAPI Correction Response: {reply.content}\n")
        print("=====================================================================")

        # Check for required field error first
        if reply.content.strip().startswith("Please mention at least one required field:"):
            logger.info(f"\nRequired field missing: {reply.content}\n")
            return {
                "type": "required_field_error", 
                "message": reply.content,
                "stop_processing": True  # Explicit flag to stop further processing
            }
        
        # Try to parse as API list (normal successful case)
        try:
            api_ans_list = ast.literal_eval(reply.content)
            logger.info(f"\nCorrect API is: {api_ans_list}\n")
            end_time = time.time()
            timer.info(f"Time taken by the Correct the API: {end_time - start_time}\n")
            return {"type": "success", "data": api_ans_list}
        
        except (ValueError, SyntaxError) as e:
            # If parsing fails, treat as error message
            logger.error(f"Could not parse API response: {reply.content}")
            return {
                "type": "error", 
                "message": reply.content,
                "stop_processing": True
            }

    async def generate_query(self, user_query, tables_schema, faqs_content):
        # system_message = SYSTEM_PROMPT.format(dialect="SQLite", input=state['user_query'], table_info=tables_schema, faqs=faqs_content)
        start_time = time.time()

        chain = SYSTEM_PROMPT | self.llm
        reply = await chain.ainvoke(
            {"user_query": user_query, "table_info": tables_schema, "faqs": faqs_content})
        # print(f"\n\n Ola krutrim answer: {reply.content}\n\n")
        new_reply = self.extract_query(reply.content)
        print("===========================================================================")
        # print(f"\n\n Generated Old Query: {reply.content}\n\n")
        print(f"\n\n Generated Query: {new_reply}\n\n")
        print("===========================================================================")
        logger.info(f"\n Generated SQL Query: {new_reply}\n")
        end_time = time.time()
        timer.info(f"Time taken by the generate query function is: {end_time - start_time}")
        return new_reply

    async def send_sql_query(self, sql_query, session_id, query_id):
        try:
            for chunk in sql_query.split():
                print(f"Chunk of the run chatbot: {chunk}")
                new_chunk = chunk + " "
                await websocket_manager.send(connection_id=session_id, message={
                    "topic": "model_stream",
                    "data": new_chunk,
                    "query_id": query_id
                })
                await asyncio.sleep(0.05)

            await websocket_manager.send(connection_id=session_id, message={
                "topic": "model_stream",
                "data": "\n",
                "query_id": query_id
            })

            return True

        except Exception as e:
            logger.exception(f"\n Exception has been occurred during the pass the sql query from the websocket: {e}\n")
            raise Exception("Exception has been occurred during the pass the sql query from the websocket")

    def is_sql(self, query: str) -> bool:
        return bool(re.match(r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\s+', query, re.IGNORECASE))

    def contains_dangerous_sql(self, sql_query):
        """
        Checks if the SQL query contains DROP, TRUNCATE, DELETE, or UPDATE statements.

        Args:
            sql_query (str): The SQL query string to check.

        Returns:
            int: 1 if a dangerous statement is found, 0 otherwise.
        """
        # Convert the query to lowercase for case-insensitive matching
        sql_query_lower = sql_query.lower()

        # Define a regular expression pattern to match dangerous SQL commands
        pattern = r'\b(drop|truncate|delete|update)\b'

        # Search for the pattern in the SQL query
        if re.search(pattern, sql_query_lower):
            return 1
        else:
            return 0    

    async def execute_query(self, sql_query, retries=0):
        try:
            if not self.is_sql(sql_query) or self.contains_dangerous_sql(sql_query):
                return "Sorry Error is Generated"

            start_time = time.time()
            q = sql_query
            # res = next(t for t in tools if isinstance(t, QuerySQLDatabaseTool)).run(q)
            DB.execute(q)

            rows = DB.fetchall()
            res = [row for row in rows]
            # If error, raise to trigger loop
            print("===========================================================================")
            print(f"\n\nExecute Query: {res}\n\n")
            print("===========================================================================")

            logger.info(f"\nExecute Query: {res}\n")
            end_time = time.time()
            timer.info(f"Time taken by the execute_query function is the {end_time - start_time}")

            if "Error:" in res:
                return "Sorry Error is Generated"

            return res

        except OperationalError as e:
            if retries <= 2:
                cnx.reconnect(attempts=3, delay=0.1)
                return await self.execute_query(sql_query, retries=retries+1)

            else:
                raise OperationalError(f"{e}")

        except Exception as e:

            if "2013: Lost connection to MySQL server during query" in str(e) and retries <= 2:
                cnx.reconnect(attempts=3, delay=0.1)
                print("Connection is reconnect successfully\n")
                logger.info("DB connection is reconnect successfully\n")
                return await self.execute_query(sql_query, retries=retries+1)

            else:
                print(f"Exception is occurred during execute query: {e}\n")
                logger.exception(f"Exception is occurred during execute query: {e}")
                return "Sorry Error is Generated"

    # async def execute_send_main(self, sql_query, session_id, query_id):
    #     results = await asyncio.gather(self.send_sql_query(sql_query, session_id, query_id), self.execute_query(sql_query))
    #
    #     return results[1]
    #
    # async def retrieve_faqs_tables_main(self, user_query):
    #     results = await asyncio.gather(self.get_faqs_content_tables(user_query), self.get_tables_schema(user_query))
    #
    #     faqs_details = results[0]
    #     tables_list = results[1]
    #
    #     faqs_content, faqs_tables = faqs_details[0], faqs_details[1]
    #
    #     return faqs_content, faqs_tables, tables_list

    async def create_sql_agent(self):
        graph = StateGraph(AgentState)
        graph.set_entry_point("init")

        ## Remove
        # Node: 1. Init
        @traceable
        async def init(state):
            """
            This function is just only the print the user query, session id, and query id for testing purpose

            Args:
                state:

            Returns:
                dict
            """

            print(f"\n\nUser Query: {state['user_query']}\n\n")
            print(f"\n\n User Session id: {state['session_id']}\n\n")
            print(f"\n\n User Query Id: {state['query_id']}")
            logger.info("========================================")
            logger.info(f"User Query: {state['user_query']}\n")
            logger.info(f"User Session id: {state['session_id']}\n")
            logger.info(f"User Query Id: {state['query_id']}")
            return {"messages": SYSTEM_PROMPT}

        ## Node 2: Rewrite User Query Based on the Chat History
        @traceable
        async def Rewrite_User_Query_based_on_history(state):
            """
            This function is used for rewrite the user query based on the history
            Args:
                state: Get the AgentState

            Returns:
                dict: Return the rewrite user query
            """

            start_time = time.time()
            
            name_chain = NAME_DETECTION_PROMPT | self.instructions_llm
            name_result = await name_chain.ainvoke({"query": state['user_query']})
            print(f"Name Detection Result: {name_result.content}")
            if name_result.content != "NONE":
                self.last_name.append(name_result.content)
                
            if not self.last_name:
                lastname = ""
            else:
                lastname = self.last_name[-1]
            print(f"Last Name List: {self.last_name}")
            
            chain = CONTEXTUALIZE_Q_PROMPT | self.instructions_llm

            history = get_session_history_with_sql_chat_history(state['session_id'])
            chat_history = []

            for message in history.messages:
                if isinstance(message, HumanMessage):
                    chat_history.append(f"Human: {message.content}")

                elif isinstance(message, AIMessage):
                    chat_history.append(f"AI: {message.content}")

            print("==================================================")
            print(f"Chat History: {chat_history}\n\n")
            print("===================================================")

            result = await chain.ainvoke({"input": state['user_query'], "chat_history": chat_history,"name": lastname})

            # conversation_chain = RunnableWithMessageHistory(
            #     chain,
            #     get_session_history_with_sql_chat_history,
            #     input_messages_key="input",
            #     history_messages_key="chat_history",
            # )

            # result = conversation_chain.invoke({"input": state['user_query']},
            #                                    config={"configurable": {'session_id': state['session_id']}})

            print("======================================================================")
            print(f"\n\n Rewrite Query: {result.content}  and type is {type(result)}\n\n")
            print("=======================================================================")

            logger.info(f"Rewrite Query: {result.content}  and type is {type(result)}\n")
            # ai_response = result['answer']['answer']
            end_time = time.time()

            timer.info("\n=======================================================================\n")
            timer.info(f"Time taken by the rewrite user query function is: {end_time - start_time}\n")

            return {"user_query": result.content}

        ## Node 3: retriever faqs and tables
        @traceable
        async def retriever_faqs_apis_and_tables(state):
            """
            This function is used for retrieve the faqs and the tables from the vectordb based on the rewrite user query.
            Args:
                state: Get the AgentState

            Returns:
                dict: return the faqs_content, faqs_tables, apis_details and merge the tables_list with the faqs_tables.
            """

            try:
                start_time = time.time()

                ## Method 1 using asyncio.run and the asyncio.gather
                # faqs_content, faqs_tables, tables_list = asyncio.run(self.retrieve_faqs_tables_main(state['user_query']))

                ## Method 2 using create task
                task1 = asyncio.create_task(self.get_faqs_content_tables(state['user_query']))
                task2 = asyncio.create_task(self.get_tables_schema(state['user_query']))
                task3 = asyncio.create_task(self.get_apis_details(state['user_query']))

                faqs_content, faqs_tables = await task1
                tables_list = await task2
                apis_details = await task3

                print("===========================================================")
                print(f"\n\n FAQS Content: {faqs_content}\n\n")
                print(f"\n\n FAQS Table: {faqs_tables}\n\n")
                print("===========================================================")

                print("===========================================================")
                print(f'\n\n Retrieve Tables list: {tables_list}\n\n')
                print("===========================================================")

                logger.info(f"\n FAQS Content: {faqs_content}\n")
                logger.info(f"\n FAQS Table: {faqs_tables}\n")
                logger.info(f"\n Retrieve Tables list: {tables_list}\n")
                logger.info(f"\n APIS Details: {apis_details}")

                imp_tables_list = list(set(tables_list + faqs_tables))

                print("===========================================================")
                print(f"\n\n After merging the faqs tables and the Retrieve tables: {imp_tables_list}\n\n")
                print("===========================================================")

                end_time = time.time()

                timer.info(f"\n Time taken in the retriever faqs and tables: {end_time - start_time}\n")

                return {"messages": imp_tables_list, "tables_info": imp_tables_list, "faqs_content": faqs_content, "apis_details": apis_details}

            except Exception as e:
                print(f"Exception has been occurred in the retriever faqs and tables: {e}")
                logger.exception(f"Exception has been occurred in the retriever faqs and tables: {e}")
                raise Exception("Exception has been occurred in the retriever faqs and tables.")

        # ## Node 4: Get the Schema information based on the retrieved tables
        # @traceable
        # async def schema_info(state):
        #     """
        #     This function is used for find the schema of the merge(actual tables + faqs tables) tables
        #     Args:
        #         state: Get the AgentState
        #
        #     Returns:
        #         dict: send the schema of the tables
        #     """
        #
        #     start_time = time.time()
        #     tables = state["messages"]
        #
        #     print("===========================================================================")
        #     print(f"\n\nList of tables: {tables}\n\n")
        #     print("===========================================================================")
        #     res = []
        #
        #
        #     for table in tables:
        #         schema_logger.info(f"Table: {table}\n Schema: {SCHEMA_DICT[table]}")
        #         res.append(SCHEMA_DICT[table])
        #
        #     schema_logger.info("======================================================================")
        #     print(f"\n Response of the schema info: {res} \n")
        #     print("===========================================================================")
        #
        #     end_time = time.time()
        #
        #     timer.info(f"Time taken by the get the schema info function is the: {end_time - start_time}\n")
        #
        #     return {"messages": res, "tables_info": res}

        ## Decide weather the go to the sql query generation or API or sql query+api
        @traceable
        async def decide_sqlquery_or_api(state):
            """
            This function is decide whether the call to the sql query or api or both based on the user query

            Args:
                state: Receive the AgentState of the graph

            Returns:
                string: either 1 or 0. 1 for(sql query and sqlquery+api) 0 for only api
            """
            print("inside the decide_sqlquery_or_api function\n")
            user_query = state['user_query']
            tables_schema = state['messages']
            apis_details = state['apis_details']
            faqs_content = state['faqs_content']

            decision = await self.main_decide_sqlquery_or_api(user_query, tables_schema, apis_details, faqs_content)

            return int(decision)

        ## Node 5: Generate the SQL Query
        @traceable
        async def generate_sql_query(state):
            """
            This function is used for the generate the SQL Query
            Args:
                state: Get the AgentState

            Returns:
                dict: return the SQL Query
            """

            tables_schema = state['messages']
            faqs_content = state["faqs_content"]
            user_query = state["user_query"]

            sql_query = await self.generate_query(user_query=user_query, tables_schema=tables_schema, faqs_content=faqs_content)

            return {"messages": tables_schema, "sql_query": sql_query}

        ## Node 6: API generation means it get the correct apis from list and then correct that api parameter and return it.
        @traceable
        async def api_correction(state):
            """
            This function handles API correction and required field validation
            """
            user_query = state['user_query']
            apis_details = state['apis_details']
            session_id = state.get('session_id')
            query_id = state.get('query_id')
            
            print("inside the api_correction function")
            
            result = await self.main_api_correction(
                user_query=user_query, 
                apis_details=apis_details, 
                state=state
            )

            # Handle required field error case
            if result["type"] == "required_field_error":
                # Store the message in history
                self.store_message(session_id, user_query, result["message"])
                
                # Send the message via websocket if needed
                if session_id and query_id:
                    await websocket_manager.send(
                        connection_id=session_id,
                        message={
                            "topic": "model_stream",
                            "data": result["message"],
                            "query_id": query_id
                        }
                    )
                    await websocket_manager.send(
                        connection_id=session_id,
                        message={
                            "topic": "model_stream_end",
                            "data": "x-finished",
                            "query_id": query_id
                        }
                    )
                
                # Return with stop_processing flag
                return {
                    "messages": result["message"], 
                    "api_error": True,
                    "stop_processing": True
                }
                
            elif result["type"] == "error":
                return {
                    "messages": result["message"], 
                    "api_error": True,
                    "stop_processing": True
                }
            else:
                return {
                    "messages": result["data"], 
                    "api_error": False
                }
    
    
        ## Node 7: API Handler that can call the api
        @traceable
        async def api_handler(state):
            """
            This function is used to handle API calls and fetch data based on the provided state.
            """
            
            # If there was an api_error, don't process further and don't send additional messages
            if state.get('api_error', False):
                session_id = state.get('session_id')
                query_id = state.get('query_id')
                error_message = state.get('messages', "Sorry, error has been generated")
                
                # Don't send websocket message here as it was already sent in api_correction
                # Just return the error state
                return {"messages": error_message, "sql_query": None}

            try:
                start_time = time.time()

                api_key = state['messages']
                if isinstance(api_key, list):
                    api_path = api_key[0]
                else:
                    api_path = api_key

                # Clean query parameters
                parsed = urlparse(api_path)
                base_path = parsed.path
                query_params = parse_qs(parsed.query)

                # Filter out NULL, None, or empty values
                clean_query = {
                    k: v[0] for k, v in query_params.items()
                    if v and v[0] and v[0].strip().upper() != "NULL"
                }

                # Rebuild path
                clean_query_str = urlencode(clean_query)
                api_path = f"{base_path}?{clean_query_str}" if clean_query_str else base_path

                url = f"http://{CRM_IP_ADDRESS}:{CRM_PORT}{api_path}"

                print(f"The Retrieved API is - {url}")

                self.store_message(
                    state['session_id'],
                    user_message=state['user_query'],
                    ai_response=api_path
                )

                response = None
                if not state.get('api_error', False):
                    response = requests.get(url)
                    print(f"Response after the API call: {response}")

                    try:
                        response_json = response.json()
                    except Exception:
                        response_json = response.text
                else:
                    response_json = None

                # Always use field extraction prompt to handle both general and specific requests
                chain = FIELD_EXTRACTION_PROMPT_TEMPLATE | self.llm
                reply = await chain.ainvoke({
                    "user_query": state['user_query'],
                    "api_response": response_json,                    
                })
                filtered_response = reply.content if hasattr(reply, "content") else reply
                result_to_return = filtered_response

                result = None
                if response.ok:
                    result = url
                    print("====================================================")
                    print(f"Result after the execution of the API: {result}")
                    print("====================================================")
                    logger.info(f"Result after the execution of the API: {result}")
                else:
                    result = "Sorry, error has been generated"
                    print(f"Error: Result after the API request: {response}")
                    logger.info(f"Error: Result after the API request: {response}")

                end_time = time.time()
                timer.info(f"Time taken by the API handler: {end_time - start_time:.2f} seconds")

                return {"messages": result_to_return, "sql_query": None}

            except Exception as e:
                print(f"Exception during API request: {e}")
                logger.exception(f"Exception during api_handler: {e}")
                return {"messages": "Sorry, error has been generated", "sql_query": None}   
            
                     
        async def condition_api_handler(state):
            """
            Determines next step based on API correction results
            """
            if state.get("stop_processing"):
                return "END"  # Stop completely for required field errors
            elif state.get("api_error"):
                return "END"  # Stop for other API errors
            return "api_handler"  # Continue to API handler if successful

        ## get the decision whether the call the API or execute the sql query
        # @traceable()
        # async def decide_sqlquery_execute_or_apicall(state):
        #     """
        #     This function is used for decision to call the api or execute the sql query based on the user query.
        #     Args:
        #         state: get the AgentState for the getting the user query, api list, sql query

        #     Returns:
        #         dict: return the decision either 1 for execute or 0 for api call
        #     """

        #     user_query = state['user_query']
        #     apis_details = state['apis_details']

        #     decision = await self.main_decide_sqlquery_execute_or_apicall(user_query, apis_details)

        #     return int(decision)

        ## Node 6: Send the SQL Query concurrently with the execution.
        @traceable
        async def send_execute_sql_query(state):
            """
            This function is send and the execute SQL Query concurrently.
            Args:
                state: Get the AgentState

            Returns:
                dict: return the execution output.
            """

            sql_query = state['sql_query']
            try:
                start_time = time.time()
                session_id = state["session_id"]
                query_id = state["query_id"]

                ## Method 1 using asyncio.run and the asyncio.gather
                # result = asyncio.run(self.execute_send_main(sql_query, session_id, query_id))

                ## Method 2 using asyncio.create_task.
                task1 = asyncio.create_task(self.send_sql_query(sql_query, session_id, query_id))
                task2 = asyncio.create_task(self.execute_query(sql_query))
                # task3 = asyncio.create_task(self.store_message(session_id, state['user_query'], state['sql_query']))

                print(f"Get session id from the sql chat history: {get_session_history_with_sql_chat_history(session_id)}")

                result1 = await task1
                result = await task2

                if self.is_sql(sql_query):
                    status = self.store_message(session_id, state['user_query'], f"The SQL Query is: {state['sql_query']} and the Executed output is: {result}")

                end_time = time.time()

                timer.info(f"Total Time taken by the send_execute_sql_query function is the: {end_time - start_time}\n")
                timer.info("===========================================================================================\n\n")

                return {"messages": result, "sql_query": sql_query}

            except Exception as e:
                print(f"Exception has been occurred: {e}")
                return {"messages": "Sorry Error is Generated", "sql_query": sql_query}

        async def condition_schema_info(state):
            return "1" if await decide_sqlquery_or_api(state) else "0"

        # async def condition_generate_sql_query(state):
        #     return "send_execute_sql_query" if await decide_sqlquery_execute_or_apicall(state) else "api_correction"

        graph.add_node("init", init)
        graph.add_node("Rewrite_User_Query_based_on_history", Rewrite_User_Query_based_on_history)
        graph.add_node("retriever_faqs_apis_and_tables", retriever_faqs_apis_and_tables)
        # graph.add_node("schema_info", schema_info)
        graph.add_node("generate_sql_query", generate_sql_query)
        graph.add_node("send_execute_sql_query", send_execute_sql_query)
        graph.add_node("api_correction", api_correction)
        graph.add_node("api_handler", api_handler)


        graph.add_edge("init", "Rewrite_User_Query_based_on_history")
        graph.add_edge("Rewrite_User_Query_based_on_history", "retriever_faqs_apis_and_tables")
        # graph.add_edge("retriever_faqs_apis_and_tables", "schema_info")
        graph.add_conditional_edges("retriever_faqs_apis_and_tables",
                                    condition_schema_info,
                                   {"1": "api_correction", "0": "generate_sql_query"})
        graph.add_edge("generate_sql_query", "send_execute_sql_query")
        # graph.add_conditional_edges("generate_sql_query",
        #                            condition_generate_sql_query,
        #                            {"send_execute_sql_query": "send_execute_sql_query", "api_correction": "api_correction"})
        # graph.add_edge("api_correction", "api_handler")
        graph.add_edge("api_handler", END)
        graph.add_edge("send_execute_sql_query", END)
        graph.add_conditional_edges("api_correction", condition_api_handler, {"END": END, "api_handler": "api_handler"})

        return graph.compile()
