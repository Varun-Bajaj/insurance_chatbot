import ast
import queue
from threading import Thread
from langchain_ollama.llms import OllamaLLM
from langchain_ollama import ChatOllama
from langchain_community.chat_models import ChatOpenAI
from langsmith import traceable
from utilities.VectorDB import emb_fn
from qdrant_client import models, QdrantClient
import chromadb
from settings.setting import *
from chromadb.config import Settings
from typing import TypedDict, Sequence
from langchain.schema.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
import re
from services.Schema_graph_algorithm import NXGraphAlgorithm
import time
from dao.chatbot_dao import *
from services.websocket_manager import websocket_manager
from typing import List
from mysql.connector import OperationalError
from services.get_bot_history import get_session_history_with_sql_chat_history, get_session_history_with_chat_messages_history


class AgentState(TypedDict, total=False):
    user_query: str
    session_id: str
    # conversation_history: dict = {}
    messages: Sequence[SystemMessage | HumanMessage | AIMessage]
    query: str
    get_important_tables: bool = True
    tables_info: List[str]
    tables_name: List[str]
    faqs_content: List[str]
    faqs_tables: List[str]
    paths: List[List[str]]

class AgentState1(TypedDict, total=False):
    user_query: str
    session_id: str
    query_id: str
    apis_details: List[str]
    # conversation_history: dict = {}
    messages: Sequence[SystemMessage | HumanMessage | AIMessage]
    sql_query: str = None
    get_important_tables: bool = True
    tables_info: str
    faqs_content: List[str]
    faqs_tables: List[str]
    relationship_paths: List[List[str]]

logger = setup_logger("Graph_Agent_chatbot_answer")
schema_logger = setup_logger("Graph_Agent_retriever_tables_schema")
timer = setup_logger("Graph_Agent_timer")


class GraphAgentChatbotManager:
    def __init__(self):
        if MODEL == 1:
            self.llm = ChatOllama(model=OLLAMA_MAIN_MODEL, base_url=OLLAMA_BASE_URL, temperature=OLLAMA_TEMPERATURE,
                                  num_ctx=OLLAMA_NUM_CTX, cache=False)

        elif MODEL == 2:
            self.llm = ChatOpenAI(api_key=KRUTRIMAI_API_KEY, base_url=KRUTRIM_BASE_URL, model=KRUTRIM_MODEL,
                                  temperature=KRUTRIM_TEMPERATURE)

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

        self.graph = NXGraphAlgorithm()
        self.G = self.graph.build_graph()

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
        if VECTOR_DB == 1:
            faqs = await self.faqs_pooled_collection.query(
                query_texts=[user_query],
                n_results=5
            )

            print("=====================FAQS=======================")
            print(f"\n\n{faqs}\n\n")
            print("================================================")

            faqs_score = faqs['distances'][0]
            faqs_vector_content = faqs['documents'][0]
            faqs_vector_tables = faqs['metadatas'][0]
            print(faqs_score)

            faqs_content = []
            faqs_tables = []
            faqs_tables_schema = []

            for i, score in enumerate(faqs_score):
                print(f"The get_faqs_content_tables: {i} and {score}")
                if score <= FAQS_CHROMADB_DISTANCE:
                    faqs_merge_content_tables = f"User_Query: {faqs_vector_content[i]}\n SQL_Query: {faqs_vector_tables[i]['sql_query']}"
                    faqs_content.append(faqs_merge_content_tables)
                    faqs_tables_schema.append(ast.literal_eval(faqs_vector_tables[i]['table_info']))
                    faqs_tables.extend(ast.literal_eval(faqs_vector_tables[i]['table_name']))

            return faqs_content, faqs_tables, faqs_tables_schema

        elif VECTOR_DB == 2:
            response = await self.faqs_qdrant_client.query_points(
                collection_name=FAQS_QDRANT_COLLECTION_NAME,
                query=self.embedding_model.encode(user_query).tolist(),
                limit=5,
                score_threshold=FAQS_THRESHOLD
            )

            print(f"\nGet FAQS content tables: {response}\n")

            hits = response.points

            faqs_content = []
            faqs_tables = []
            faqs_tables_schema = []

            print("=============================================")

            for hit in hits:
                pyld = hit.payload
                print(f"\n\nUser Query: {pyld['user_query']}\n\n")
                print(f"\n\n Score: {hit.score}\n\n")
                payload = hit.payload
                content = f"User_Query: {payload['user_query']}\n SQL_Query: {payload['sql_query']}"
                faqs_content.append(content)
                faqs_tables_schema.extend(payload['content'])
                faqs_tables.extend(payload['table_name'])

            print("============================================")

            return faqs_content, faqs_tables, faqs_tables_schema

        return None

    async def get_apis_details(self, user_query):
        if VECTOR_DB == 1:
            apis = await self.apis_pooled_collection.query(
                query_texts=[user_query],
                n_results=5
            )

            # print("=====================APIS=======================")
            # print(f"\n\n{apis}\n\n")
            # print("================================================")

            apis_score = apis['distances'][0]
            apis_vector_description = apis['documents'][0]
            apis_vector_name_endpoint = apis['metadatas'][0]
            print(apis_score)

            apis_details = []

            for i, score in enumerate(apis_score):
                print(f"The get_faqs_content_tables: {i} and {score}")
                if score <= API_CHROMADB_DISTANCE:
                    api_detail = f"API_Name: {apis_vector_name_endpoint[i]['Name']}\n API_Endpoint: {apis_vector_name_endpoint[i]['Endpoint']}\n API_Description: {apis_vector_name_endpoint[i]['Description']}"
                    apis_details.append(api_detail)

            return apis_details

        elif VECTOR_DB == 2:
            response = await self.apis_qdrant_client.query_points(
                collection_name=APIS_QDRANT_COLLECTION_NAME,
                query=self.embedding_model.encode(user_query).tolist(),
                limit=1,
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
                print(f"Page_Content: {payload['Page_content']}\n\n")
                print("======================================")
                content = f"API_Name: {payload['Name']}\n API_Endpoint: {payload['Endpoint']}\n API_Description: {payload['Description']}"
                apis_details.append(content)

            print("============================================")

            return apis_details

        return None

    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = ChatMessageHistory()
            print("New session created.")

        else:
            print("Existing session retrieved.")

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

    async def retrieve_tables(self, user_query):
        try:
            if VECTOR_DB == 1:
                tables_list = []
                tables_content = []
                imp_tables = await self.pooled_collection.query(
                    query_texts=[user_query],
                    n_results=10,
                    ## from vectordb i am extracting the top 10 similar table and found the schema of those tables.
                )

                tables = imp_tables['metadatas'][0]
                tables_content = imp_tables['documents'][0]

                for i in range(len(tables_content)):
                    tables_list.append(tables[i]['table_name'])
                    tables_content.append(tables_content[i])

                # imp_tables_list = [i['source'] for i in tables]

                return tables_list, tables_content

            elif VECTOR_DB == 2:
                tables_list = []
                tables_content = []
                response = await self.qdrant_client.query_points(
                    collection_name=QDRANT_COLLECTION_NAME,
                    query=self.embedding_model.encode(user_query).tolist(),
                    limit=20,
                    score_threshold=0.60,
                )

                print(f"\nGet tables: {response}\n")

                hits = response.points

                for hit in hits:
                    di = hit.payload
                    tables_content.append(di['Content'])
                    tables_list.append(di['Table_name'])

                return tables_list, tables_content

            return []

        except Exception as e:
            print(f"Exception has been occurred in the get tables schema function is: {e}\n")
            logger.exception(f"Exception has been occurred in the get tables schema function is: {e}\n")
            raise Exception("Exception has been occurred in the get tables schema function.")

    async def main_decide_sqlquery_or_api(self, user_query, tables_schema, apis_details, faqs_content):
        start_time = time.time()

        chain = DECISION_SQLQUERY_OR_API_PROMPT | self.llm

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

    async def main_api_correction(self, user_query, apis_details):
        start_time = time.time()

        chain = API_CORRECTION_PROMPT | self.llm

        reply = await chain.ainvoke(
            {"user_query": user_query, "apis_details": apis_details}
        )

        print("======================================================================")
        print(f"\nCorrect API: {reply.content}\n")
        print("=====================================================================")

        logger.info(f"\n Correct API is: {reply.content}\n")

        end_time = time.time()

        timer.info(f"Time taken by the Correct the API: {end_time - start_time}\n")

        return reply.content

    async def generate_query(self, user_query, tables_schema, faqs_content, relationship_paths):
        # system_message = SYSTEM_PROMPT.format(dialect="SQLite", input=state['user_query'], table_info=tables_schema, faqs=faqs_content)
        start_time = time.time()

        chain = SYSTEM_PROMPT_2 | self.llm
        reply = await chain.ainvoke(
            {"user_query": user_query, "table_info": tables_schema, "faqs": faqs_content, "relationship_paths": relationship_paths})
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

    async def execute_query(self, sql_query, retires=0):
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
            if retires <= 2:
                cnx.reconnect(attempts=3, delay=0.1)
                return await self.execute_query(sql_query, retires=retires+1)

            else:
                raise OperationalError(f"{e}")

        except Exception as e:
            print(f"Exception is occurred during execute query: {e}\n")
            logger.exception(f"Exception is occurred during execute query: {e}")
            return "Sorry Error is Generated"

    # async def execute_send_main(self, sql_query, session_id, query_id):
    #     # task1 = asyncio.create_task(self.send_sql_query(sql_query, session_id, query_id))
    #     # task2 = asyncio.create_task(self.execute_query(sql_query))

    #     results = await asyncio.gather(self.send_sql_query(sql_query, session_id, query_id), self.execute_query(sql_query))

    #     return results[1]

    # async def retrieve_faqs_tables_main(self, user_query):
    #     # task1 = asyncio.create_task(self.get_faqs_content_tables(state['user_query']))
    #     # task2 = asyncio.create_task(self.retrieve_tables(state['user_query']))

    #     results = await asyncio.gather(self.get_faqs_content_tables(user_query), self.retrieve_tables(user_query))

    #     faqs_details = results[0]
    #     tables_list = results[1]

    #     faqs_content, faqs_tables = faqs_details[0], faqs_details[1]

    #     return faqs_content, faqs_tables, tables_list

    async def target_tables_from_sql_lookup(self, sql_query, tables_list):
        chain = TARGET_TABLE_FROM_SQL_PROMPT | self.llm
        result = await chain.ainvoke({"SQL_QUERY": sql_query, "SCHEMA_BLOCK": tables_list})
        return result.content

    def get_tables_schema(self, tables, q):
        res = []

        for table in tables:
            schema_logger.info(f"Table: {table}\n Schema: {SCHEMA_DICT[table]}")
            res.append(SCHEMA_DICT[table])

        q.put(res)

    async def create_sql_agent(self):
        graph = StateGraph(AgentState1)
        graph.set_entry_point("init")

        # Node: 1. Init
        @traceable
        async def init(state):
            """
            This function is just only the print the user query, session id, and query id for testing purpose

            Args:
                state: Get the AgentState

            Returns:
                dict: return the normal prompt
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

            chain = CONTEXTUALIZE_Q_PROMPT | self.llm

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

            result = await chain.ainvoke({"input": state['user_query'], "chat_history": chat_history})

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

        ## Node 3: Deside Which is Path choose Either API or SQL Query Generation with executing or SQL Query generation + API.

        ## Node 3: retriever faqs and tables
        @traceable
        async def retriever_faqs_apis_tables_and_relationship_paths(state):
            """
            This function is used for retrieve the faqs and the tables from the vectordb based on the rewrite user query. and find the relationship paths between two tables.
            Args:
                state: Get the AgentState

            Returns:
                dict: return the faqs_content, faqs_tables, and merge the tables_list with the faqs_tables.
            """

            try:
                start_time = time.time()

                ## Method 1 using asyncio.run and the asyncio.gather
                # faqs_content, faqs_tables, tables_list = asyncio.run(self.retrieve_faqs_tables_main(state['user_query']))

                ## Method 2 using create task
                task1 = asyncio.create_task(self.get_faqs_content_tables(state['user_query']))
                task2 = asyncio.create_task(self.retrieve_tables(state['user_query']))
                task3 = asyncio.create_task(self.get_apis_details(state['user_query']))

                faqs_content, faqs_tables, faqs_tables_schema = await task1
                tables_list, tables_content = await task2
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

                # Find the relationship paths between tables
                q = queue.Queue()
                self.graph.expand_path_graph(self.G, imp_tables_list, q)

                # print("The relationship path is extract\n\n")
                results = [q.get() for _ in range(0, 1)]
                # print(f"The results is : {results[0]}\n\n")
                paths = results[0]

                print("===========================================================================")
                logger.info(f"\n Relationship Paths of the tables: {paths}\n")
                print(f"\n Relationship Paths of the tables: {paths}\n")
                print("===========================================================================")

                ## merge the two tables if the same
                imp_tables_info = list(set(tables_content + faqs_tables_schema))

                print("===========================================================")
                print(f"\n\n After merging the faqs tables and the Retrieve tables: {imp_tables_list}\n\n")
                print("===========================================================")

                end_time = time.time()

                timer.info(f"\n Time taken in the retriever faqs and tables: {end_time - start_time}\n")

                return {"messages": imp_tables_info, "tables_info": imp_tables_info, "faqs_content": faqs_content, "apis_details": apis_details, "relationship_paths": paths}

            except Exception as e:
                print(f"Exception has been occurred in the retriever faqs and tables: {e}")
                logger.exception(f"Exception has been occurred in the retriever faqs and tables: {e}")
                raise Exception("Exception has been occurred in the retriever faqs and tables.")

        ## Node 4: Get the Schema information based on the retrieved tables
        # @traceable
        # async def schema_info(state):
        #     """
        #     This function is used for find the schema and the path between two tables(each) of the merge(actual tables + faqs tables) tables.
        #     Args:
        #         state: Get the AgentState

        #     Returns:
        #         dict: send the schema of the tables
        #     """
        #     start_time = time.time()
        #     tables = state["messages"]

        #     print("===========================================================================")
        #     print(f"\n\nList of tables: {tables}\n\n")
        #     print("===========================================================================")

        #     q = queue.Queue()

        #     t1 = Thread(target=self.get_tables_schema, args=(tables,q))
        #     t2 = Thread(target=self.graph.expand_path_graph(self.G, tables, q))

        #     t1.start()
        #     t2.start()

        #     t1.join()
        #     t2.join()

        #     results = [q.get() for _ in range(0, 2)]

        #     res = results[0]
        #     paths = results[1]

        #     schema_logger.info("======================================================================")
        #     schema_logger.info(f"\n Response of the schema info: {res} \n")
        #     print(f"\n Response of the schema info: {res} \n")
        #     print("===========================================================================")

        #     logger.info(f"\n Relationship Paths of the tables: {paths}\n")
        #     print(f"\n Relationship Paths of the tables: {paths}\n")
        #     print("===========================================================================")

        #     end_time = time.time()

        #     timer.info(f"Time taken by the get the schema info function is the: {end_time - start_time}\n")

        #     return {"messages": res, "tables_info": res, "relationship_paths": paths}

        ## Decide weather the go to the sql query generation or API or sql query+api
        @traceable
        async def decide_sqlquery_or_api(state):
            """
            This function is decide whether the call to the sql query or api or both based on the user query

            Args:
                state: Receive the Agentstate of the graph

            Returns:
                string: either 1 or 0. 1 for(sql query and sqlquery+api) 0 for only api
            """

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
            relationship_paths = state["relationship_paths"]

            sql_query = await self.generate_query(user_query=user_query, tables_schema=tables_schema, faqs_content=faqs_content, relationship_paths=relationship_paths)

            return {"messages": tables_schema, "sql_query": sql_query}

        ## Node 6: API generation means it get the correct apis from list and then correct that api parameter and return it.
        @traceable
        async def api_correction(state):
            """
            This function is used for choose the correct api and set its parameter based on the user query.

            Args:
                state: take the AgentState of the graph that contains the list of value

            Returns:
                dict: return the api by correcting the parameter value based on the user query.
            """

            user_query = state['user_query']
            apis_details = state['apis_details']
            # sql_query = state['sql_query']

            api_key = await self.main_api_correction(user_query=user_query, apis_details=apis_details)

            return {"messages": api_key}

        ## Node 7: API Handler that can call the api
        @traceable
        async def api_handler(state):
            """
            This function is used for api handler that can call the api and fetch the data.

            Args:
                state: take the AgentState of the graph that contains the api

            Returns:
                dict: return the data after api call.
            """
            try:
                start_time = time.time()

                api_key = state['messages']

                url = f"http://{CRM_IP_ADDRESS}:{CRM_PORT}{api_key}"

                print(f"The Retrieved API is - {url}")

                status = self.store_message(state['session_id'], user_message=state['user_query'], ai_response=url)

                ##response = requests.post(url=url)

                result = None

                # if response.ok:
                #     result = url
                #     #result = response.text.strip()
                #     print("====================================================")
                #     print(f"Result after the execution of the API: {result}\n")
                #     print("====================================================")
                #     logger.info(f"Result after the execution of the API: {result}\n")
                #
                # else:
                #     result = "Sorry Error has been generated"
                #     print(f"Error: Result after the api request: {response}\n")
                #     logger.info(f"Error; Result after the api request: {response}\n")

                end_time = time.time()

                timer.info(f"Time taken by the api handler function that execute api: {end_time - start_time}\n")

                return {"messages": url, "sql_query": None}

            except Exception as e:
                print(f"Exception has been occurred during hit the api request is: {e}\n")
                logger.exception(f"Exception has been occurred during api handler: {e}\n")
                return {"messages": "Sorry Error has been generated", "sql_query": None}

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

        ## Node 6: Send the SQL Query concurrently with the execute.
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
                # tables_schema = state["messages"]
                # faqs_content = state["faqs_content"]
                # user_query = state["user_query"]
                session_id = state["session_id"]
                query_id = state["query_id"]

                # sql_query = self.generate_query(user_query, tables_schema, faqs_content)

                task1 = asyncio.create_task(self.send_sql_query(sql_query, session_id, query_id))
                task2 = asyncio.create_task(self.execute_query(sql_query))

                if self.is_sql(sql_query):
                    status = self.store_message(session_id, state['user_query'], state['sql_query'])

                print(f"Get session id from the sql chat history: {get_session_history_with_sql_chat_history(session_id)}")

                result1 = await task1
                result = await task2

                # result = asyncio.run(self.execute_send_main(sql_query, session_id, query_id))

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
        graph.add_node("retriever_faqs_apis_tables_and_relationship_paths", retriever_faqs_apis_tables_and_relationship_paths)
        # graph.add_node("schema_info", schema_info)
        graph.add_node("generate_sql_query", generate_sql_query)
        graph.add_node("send_execute_sql_query", send_execute_sql_query)
        graph.add_node("api_correction", api_correction)
        graph.add_node("api_handler", api_handler)

        graph.add_edge("init", "Rewrite_User_Query_based_on_history")
        graph.add_edge("Rewrite_User_Query_based_on_history", "retriever_faqs_apis_tables_and_relationship_paths")
        # graph.add_edge("retriever_faqs_apis_and_tables", "schema_info")
        graph.add_conditional_edges("retriever_faqs_apis_tables_and_relationship_paths",
                                    condition_schema_info,
                                    {"1": "api_correction", "0": "generate_sql_query"})
        # graph.add_conditional_edges("generate_sql_query",
        #                             condition_generate_sql_query,
        #                             {"send_execute_sql_query": "send_execute_sql_query",
        #                              "api_correction": "api_correction"})
        graph.add_edge("generate_sql_query", "send_execute_sql_query")
        graph.add_edge("api_correction", "api_handler")
        graph.add_edge("api_handler", END)
        graph.add_edge("send_execute_sql_query", END)

        return graph.compile()






### This is another graph which is find the source table and the target table from the user query then find the path between them using graph but it is not as much as optimized.

# def create_sql_agent(self):
    # graph = StateGraph(AgentState)
    # graph.set_entry_point("init")
    #
    # # Node: 1. Init
    # @traceable
    # def init(state):
    #     print(f"\n\nUser Query: {state['user_query']}\n\n")
    #     print(f"\n\n User Session id: {state['session_id']}\n\n")
    #     logger.info("========================================")
    #     logger.info(f"User Query: {state['user_query']}\n")
    #     logger.info(f"User Session id: {state['session_id']}\n")
    #     return {"messages": SYSTEM_PROMPT}
    #
    # graph.add_node("init", init)
    #
    # ## Node 2: Rewrite User Query Based on the Chat History
    # @traceable
    # def Rewrite_User_Query_based_on_history(state):
    #     chain = CONTEXTUALIZE_Q_PROMPT | self.llm
    #
    #     conversation_chain = RunnableWithMessageHistory(
    #         chain,
    #         self.get_session_history,
    #         input_messages_key="input",
    #         history_messages_key="chat_history",
    #     )
    #
    #     result = conversation_chain.invoke({"input": state['user_query']},
    #                                        config={"configurable": {'session_id': state['session_id']}})
    #
    #     print("======================================================================")
    #     print(f"\n\n Rewrite Query: {result.content}  and type is {type(result)}\n\n")
    #     print("=======================================================================")
    #
    #     logger.info(f"Rewrite Query: {result.content}  and type is {type(result)}\n")
    #     # ai_response = result['answer']['answer']
    #
    #     return {"user_query": result.content}
    #
    # graph.add_node("Rewrite_User_Query_based_on_history", Rewrite_User_Query_based_on_history)
    # graph.add_edge("init", "Rewrite_User_Query_based_on_history")
    #
    # ## Node 3: Check User Query is match in any FAQS
    # @traceable
    # def is_in_FAQS(state):
    #     user_query = state['user_query']
    #     faqs_content, faqs_tables = self.get_faqs_content_tables(user_query)
    #
    #     print("=====================================================================")
    #     print(f"\n\n FAQS Content: {faqs_content}\n\n")
    #     print(f"\n\n FAQS Table: {faqs_tables}\n\n")
    #     print("=====================================================================")
    #
    #     logger.info(f"\n FAQS Content: {faqs_content}\n")
    #     logger.info(f"\n FAQS Table: {faqs_tables}\n")
    #
    #     return {"user_query": user_query, "faqs_content": faqs_content, "faqs_tables": faqs_tables}
    #
    # graph.add_node("is_in_faqs", is_in_FAQS)
    # graph.add_edge("Rewrite_User_Query_based_on_history", "is_in_faqs")
    #
    # ## Node 4: Get the tables from the retriever
    # @traceable
    # def list_tables(state):
    #     faqs_table_list = state['faqs_tables']
    #     imp_tables_list = []
    #
    #     if VECTOR_DB == 1:
    #         imp_tables = self.pooled_collection.query(
    #             query_texts=[state['user_query']],
    #             n_results=10,
    #
    #             ## from vectordb i am extracting the top 10 similar table and found the schema of those tables.
    #         )
    #
    #         tables = imp_tables['metadatas'][0]
    #
    #         for i in tables:
    #             if i['source'] not in faqs_table_list:
    #                 imp_tables_list.append(i['source'])
    #         # imp_tables_list = [i['source'] for i in tables]
    #         imp_tables_list.extend(faqs_table_list)
    #
    #     elif VECTOR_DB == 2:
    #         hits = self.qdrant_client.query_points(
    #             collection_name=QDRANT_COLLECTION_NAME,
    #             query=self.embedding_model.encode(state['user_query']).tolist(),
    #             limit=10,
    #             score_threshold=0.60,
    #         ).points
    #
    #         imp_tables_list = []
    #
    #         for hit in hits:
    #             di = hit.payload
    #             if di['Table_name'] not in faqs_table_list:
    #                 imp_tables_list.append(di['Table_name'])
    #
    #         imp_tables_list.extend(faqs_table_list)
    #
    #     logger.info(f"Retrieve Tables list: {imp_tables_list}\n")
    #
    #     return {"messages": imp_tables_list}
    #
    # graph.add_node("list_tables", list_tables)
    # graph.add_edge("is_in_faqs", "list_tables")
    #
    # ## Node 5: Get the Schema information based on the retrieved tables
    # @traceable
    # def schema_info(state):
    #     tables = state["messages"]
    #
    #     # if type(tables) is str:
    #     #     table_list = json.loads(tables)
    #     #     print(table_list)
    #
    #     print("===========================================================================")
    #     print(f"\n\nList of tables: {tables}\n\n")
    #     print("===========================================================================")
    #     res = []
    #
    #     for table in tables:
    #         schema_logger.info(f"Table: {table}\n Schema: {SCHEMA_DICT[table]}")
    #         res.append(SCHEMA_DICT[table])
    #
    #     schema_logger.info("======================================================================")
    #     print(f"\n Response of the schema info: {res} \n")
    #     print("===========================================================================")
    #
    #     return {"messages": res, "tables_name": tables}
    #
    # graph.add_node("schema_info", schema_info)
    # graph.add_edge("list_tables", "schema_info")
    #
    # ## Node 6: Generate SQL Query Based on the retrieved tables schema, faqs and the user query
    # @traceable
    # def generate_query(state):
    #     tables_schema = state["messages"]
    #     faqs_content = state["faqs_content"]
    #     # system_message = SYSTEM_PROMPT.format(dialect="SQLite", input=state['user_query'], table_info=tables_schema, faqs=faqs_content)
    #     chain = SYSTEM_PROMPT | self.llm
    #     reply = chain.invoke(
    #         {"user_query": state['user_query'], "table_info": tables_schema, "faqs": faqs_content})
    #     # print(f"\n\n Ola krutrim answer: {reply.content}\n\n")
    #     new_reply = self.extract_query(reply.content)
    #     print("===========================================================================")
    #     # print(f"\n\n Generated Old Query: {reply.content}\n\n")
    #     print(f"\n\n Generated Query: {new_reply}\n\n")
    #     print("===========================================================================")
    #     logger.info(f"\n Generated SQL Query: {new_reply}\n")
    #     return {"messages": new_reply, "query": new_reply, "tables_info": tables_schema}
    #
    # graph.add_node("generate_query", generate_query)
    # graph.add_edge("schema_info", "generate_query")
    #
    # ## Node 7: Check the SQL Query is it write or wrong
    # # @traceable
    # # def check_query(state):
    # #     q = state["query"]
    # #     # query_checker_prompt = QUERY_CHECKER_PROMPT.format(query=q, dialect="sqlite",
    # #     #                                                    table_info=state['tables_info'])
    # #     chain = QUERY_CHECKER_PROMPT | self.llm
    # #     checked = chain.invoke({"query": q, "dialect": "sqlite", "table_info": state['tables_info']})
    # #     # print(f"\n\n Ola krutrim answer: {checked.content}\n\n")
    # #     new_checked = self.extract_query(checked.content)
    # #     print("===========================================================================")
    # #     print(f"\n\n Checked: {new_checked}\n\n")
    # #     # print(f"\n\n New Checked: {new_checked}\n\n")
    # #     print("===========================================================================")
    # #     logger.info(f"\n Checked: {new_checked}\n")
    # #     return {"messages": new_checked, "query": new_checked}
    # #
    # # graph.add_node("check_query", check_query)
    # # graph.add_edge("generate_query", "check_query")
    #
    # ## Node 8: extract source and target tables
    # def extract_source_target_tables(state):
    #     sql_query = state["query"]
    #     tables_list = state["tables_name"]
    #
    #     target_table = self.target_tables_from_sql_lookup(sql_query, tables_list)
    #     final_target_table = self.extract_and_parse_json_block(target_table)
    #
    #     logger.info(f"\n Target tables retrieved: {final_target_table['Target Table']}\n")
    #     print(f"\n Target Tables retrieved: {final_target_table['Target Table']}")
    #
    #     return {"messages": final_target_table['Target Table']}
    #
    # graph.add_node("extract_source_target_tables", extract_source_target_tables)
    # graph.add_edge("generate_query", "extract_source_target_tables")
    #
    # ## Node 9: run graph algorithm
    # def graph_algorithm(state):
    #     tables_list = state['tables_name']
    #     source_tables_list = state['tables_name'][:5]
    #     target_tables_list = [state['messages']]
    #     final_target_tables = []
    #
    #     for table in target_tables_list:
    #         if table in tables_list and table not in final_target_tables:
    #             final_target_tables.append(table)
    #
    #     graph_algo_manager = GraphAlgorithm(source_tables_list, final_target_tables)
    #
    #     paths = graph_algo_manager.algorithm2()
    #
    #     logger.info(f"\n The Paths find by the algorithms: {paths}\n")
    #
    #     print(f"\n The Paths find by the algorithms: {paths}\n")
    #
    #     return {"messages": paths, "paths": paths}
    #
    # graph.add_node("Graph_Algorithm", graph_algorithm)
    # graph.add_edge("extract_source_target_tables", "Graph_Algorithm")
    #
    # ## Node 10: Generate the SQL Query based on the given path
    # def Regenerate_SQL_Query_based_on_paths(state):
    #     tables_list = state['tables_name']
    #     paths = state['paths']
    #     merge_final_tables = set()
    #
    #     for tables_list in paths:
    #         for table in tables_list:
    #             merge_final_tables.add(table)
    #
    #     table_info = []
    #
    #     for table in merge_final_tables:
    #         table_info.append(SCHEMA_DICT[table])
    #
    #     chain = SYSTEM_PROMPT | self.llm
    #
    #     result = chain.invoke({"user_query": state['user_query'], "table_info": table_info, "Join_paths": paths, "faqs": state['faqs_content']})
    #
    #     logger.info(f"\n The Generated SQL Query using graph algorithm {result.content}\n")
    #     print(f"\n The Generated SQL Query using graph algorithm {result.content}\n")
    #
    #     return {"messages": result.content, "query": result.content}
    #
    # graph.add_node("regenerate_sql_query_based_on_paths", Regenerate_SQL_Query_based_on_paths)
    # graph.add_edge("Graph_Algorithm", "regenerate_sql_query_based_on_paths")
    #
    # def is_dml_query(state) -> bool:
    #     """
    #     Checks if the provided SQL query is a DML statement.
    #     Returns True if it is, False otherwise.
    #     """
    #     dml_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE', 'ALTER']
    #     # Remove leading/trailing whitespace and convert to uppercase for uniformity
    #     sql = state['messages']
    #     sql_cleaned = sql.strip().upper()
    #     # Use regular expressions to match the beginning of the query
    #     dml_flag = any(re.match(rf'^{kw}\b', sql_cleaned) for kw in dml_keywords)
    #
    #     if dml_flag:
    #         self.store_message(state['session_id'], state['user_query'], state['messages'])
    #         return True
    #
    #     else:
    #         return False
    #
    # ## Node 11: Execute SQL Query
    # @traceable
    # def execute_query(state):
    #
    #     try:
    #         q = state["query"]
    #         # res = next(t for t in tools if isinstance(t, QuerySQLDatabaseTool)).run(q)
    #         DB.execute(q)
    #         res = [row for row in DB.fetchall()]
    #         # If error, raise to trigger loop
    #         print("===========================================================================")
    #         print(f"\n\nExecute Query: {res}\n\n")
    #         print("===========================================================================")
    #
    #         logger.info(f"\nExecute Query: {res}\n")
    #
    #         self.store_message(state['session_id'], state['user_query'], f"{res}")
    #
    #         if "Error:" in res:
    #             return {"messages": "Sorry Error is Generated", "query": state['query']}
    #
    #         return {"messages": res, "query": state['query']}
    #
    #     except Exception as e:
    #         logger.exception(f"Exception is occurred during execute query: {e}")
    #         return {"messages": "Sorry Error is Generated", "query": state['query']}
    #
    # graph.add_node("execute_query", execute_query)
    #
    # graph.add_conditional_edges(
    #     "regenerate_sql_query_based_on_paths",
    #     lambda s: "execute_query" if not is_dml_query(s) else "end",
    #     {"execute_query": END, "end": END}
    # )
    #
    # return graph.compile()
