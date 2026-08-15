from langchain_ollama.llms import OllamaLLM
from langchain_ollama import ChatOllama
from services.nemoguardrails_manager import NemoGuardrailsManagerOllama, NemoGuardrailsManagerOLA
from qdrant_client import models, QdrantClient
import chromadb
from settings.setting import *
from chromadb.config import Settings
from typing import TypedDict, Sequence
from langchain.schema.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
import time
from dao.chatbot_dao import *
from logs.logger_setup import *
from Model.analysis_model import *
from services.websocket_manager import websocket_manager
from typing import Dict, List
from services.CRMChatbotFlow import CRMChatbotManager
from services.CRMChatbotGraphFlow import GraphAgentChatbotManager
# from pathlib import Path
# from langsmith import Client
# #from langchain.smith import traceable
# from langchain.callbacks.tracers import LangChainTracer
#
#
# os.environ["LANGCHAIN_API_KEY"]="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"
# ls_client = Client()
#KRUTRIMAI_API_KEY = ""

logger = setup_logger("chatbot_answer")
# schema_logger = setup_logger("retriever_tables_schema")

class ChatbotManager:
    def __init__(self):
        self.guardrails_manager = NemoGuardrailsManagerOLA()
        # self.greeting_llm = ChatOllama(model=GREETINGS_MAIN_MODEL, base_url=GREETINGS_BASE_URL, temperature=GREETINGS_TEMPERATURE, num_ctx=GREETINGS_NUM_CTX, cache=False)
        self.greeting_llm = None

        if APPROACH == 1:
            self.agent_manager = CRMChatbotManager()

        elif APPROACH == 2:
            self.agent_manager = GraphAgentChatbotManager()


    async def _is_query_valid_from_nemoguardrails(self, question: str) -> bool:
        guardrails_response = await self.guardrails_manager.run_guardrails(user_input=question)
        logger.info(f"guardrails_response {guardrails_response}")
        if guardrails_response == "Valid":
            return True
        return False

    ## Check Greetings
    # def check_greetings(self, user_query):
    #     # greeting_prompt = GREETINGS_CHECK_PROMPT.format(user_input=user_query)
    #     chain = GREETINGS_CHECK_PROMPT | self.greeting_llm
    #     answer = chain.invoke({"user_message": user_query})
    #     answer = answer.content
    #     print("===============================================================")
    #     print(f"\n\n Check greeting answer: {answer} \n\n")
    #     print("===============================================================")

    #     logger.info(f"\n Check greeting answer: {answer} \n")

    #     found = answer.find('1')

    #     print(f"\n\n Found greetings: {found}\n\n")

    #     if found != -1:
    #         return True

    #     else:
    #         return False

    ## Answer greetings
    def greetings_answer(self, user_query):
        prompt = ChatPromptTemplate.from_messages([
                    ("system", """ You are an intelligent agent designed to interact with a SQL database.\n Give the answer of the general inquiries and greetings appropriately.
                        - If the user asks a greeting or a casual question, respond naturally.
                        - If the user asks for help with multiple questions, acknowledge the request and encourage them to proceed.\n"""),
                    ("human", "{user_message}"),
                ])

        chain = prompt | self.greeting_llm
        response = chain.invoke({"user_message": user_query})

        print("============================================================")
        print(f"\n\n Greetings answer: {response.content} \n\n")
        print("============================================================")

        logger.info(f"\n Greeting answer: {response.content}\n")
        return response.content


    async def Agent(self):
        return await self.agent_manager.create_sql_agent()

manager = ChatbotManager()

async def run_chatbot(user_query:str, session_id:str, query_id: str, analysis_obj, db, start_time: float):
    print("Successfully enter into run chatbot")
    try:
        agent = await manager.Agent()
        final_result = []
        
        async for step in agent.astream(
                {"user_query": user_query,
                 "session_id": session_id,
                 "query_id": query_id}, stream_mode="updates"
        ):
            final_result.append(step)

        if list(final_result[-1].keys())[0] == "send_execute_sql_query":
            answer = final_result[-1]['send_execute_sql_query']['sql_query']
            executed_output = final_result[-1]['send_execute_sql_query']['messages']

        else:
            if 'api_handler' in final_result[-1]:
                answer = final_result[-1]['api_handler']['sql_query']
                executed_output = final_result[-1]['api_handler']['messages']
            else:
                # Early exit (required field error), just use the AI reply
                answer = None
                executed_output = final_result[-1].get('messages', 'Sorry, an error occurred.')

        if answer is not None:
            final_output = f"SQL Query is {answer} \n and the Executed output is {executed_output}"
        else:
            final_output = f"the Executed output is {executed_output}"

        # Check if this is an early exit due to api_error (required field error)
        if final_result[-1].get("api_error"):
            # Message already sent in api_correction, just return without sending more messages
            return {"answer": executed_output, "query": user_query}

        # Only send output if not an early exit and not an error
        if executed_output != 'Sorry Error is Generated' and not final_result[-1].get("api_error"):
            executed_output = f"{executed_output}"
            for chunk in executed_output.split():
                print(f"Chunk of the run chatbot: {chunk}")
                new_chunk = chunk + " "
                await websocket_manager.send(connection_id=session_id, message={
                    "topic": "model_stream",
                    "data": new_chunk,
                    "query_id": query_id
                })
                await asyncio.sleep(0.05)

            await websocket_manager.send(connection_id=session_id, message={
               "topic": "model_stream_end",
               "data": "x-finished",
               "query_id": query_id,
            })

        add_qa(analysis=analysis_obj, answer=final_output, db=db)
        return {"answer": final_output, "query": user_query}

    except Exception as e:
        print(f"Exception has been occurred in run_chatbot {e}\n")
        logger.exception(f"Exception has been occurred in run_chatbot {e}\n")
        return f"Exception has been occurred {e}"



async def send_default_response(session_id: str, query_id: str, query: str) -> Dict[str, str]:
    """Handles invalid queries with a default response."""
    try:
        default_answer = "Sorry, I can't assist you with that."
        await websocket_manager.send(connection_id=session_id, message={
            "topic": "model_stream",
            "data": default_answer,
            "query_id": query_id,
        })
        return {"answer": default_answer, "query": query}

    except Exception as e:
        logger.exception(f"Exception has been occurred from nemo guardrails response: {e}")
        print(f"Exception has been occurred from nemo guardrails response: {e}")


async def process_query_with_guardrails(user_id, session_id, query_id, db) -> Dict[str, str]:
    """Processes the query with validation and streaming response."""
    # self.is_busy = True
    start_time = time.time()
    try:
        # logger.info(f"Processing query_id {query_id} for user {user_id} in session {session_id} on model {self.model_id}.")

        analysis_obj: Analysis = db.get(Analysis, query_id)

        if not analysis_obj:
            print(f"Query Id {query_id} not found in the database.")
            logger.error(f"Query ID {query_id} not found in the database.")
            return {"answer": "", "query": ""}

        query = analysis_obj.question

        # config = {"configurable": {"session_id": f"{user_id}-{session_id}"},"callbacks": [tracer]}

        response_from_nemo_guardrails = await manager._is_query_valid_from_nemoguardrails(query)
        print_response_for_nemo_guardrails = "❌" if not response_from_nemo_guardrails else "✅"
        print(f"For query '{query}' From Nemo Guardrails : {print_response_for_nemo_guardrails}")
        logger.info(f"For query '{query}' From Nemo Guardrails : {print_response_for_nemo_guardrails}")
        if not query or not response_from_nemo_guardrails:
            return await send_default_response(session_id,query_id, query)

        # logger.debug(f"Processing query through rag chain...")
        return await run_chatbot(query, session_id, query_id, analysis_obj, db, start_time)

    except Exception as e:
        logger.exception(f"Exception for conversational rag chain {e}\n")
        print(f"Exception for conversational rag chain {e}\n")
        # logger.exception(f"Exception for conversational rag chain {e}")
        return {"answer": "", "query": ""}

    finally:
        logger.info("Process Query with guardrails")
        print("process Query with guardrails")
