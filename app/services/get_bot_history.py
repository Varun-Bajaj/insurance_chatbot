from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

# from langchain_core.messages import HumanMessage
# from langchain_core.messages.ai import AIMessage

from settings.setting import *
# from sqlalchemy.ext.asyncio import create_async_engine
from logs.logger_setup import setup_logger

logger = setup_logger("Normal_Agent_chatbot_answer")

conversation_history = {}
# Function to get session history
def get_session_history_with_sql_chat_history(session_id: str):
    try:
        # async_engine = create_async_engine(SYNC_DB_URL)
        history = SQLChatMessageHistory(
            session_id=session_id, connection=SYNC_DB_URL, table_name="chat_history", async_mode=False
        )
        stored_messages = history.messages

        # print(f"Get session history with sql chat history: {stored_messages}\n")

        if len(stored_messages) > MAINTAIN_CONVERSATION_HISTORY_COUNT:
            history.clear()
            stored_messages = stored_messages[-MAINTAIN_CONVERSATION_HISTORY_COUNT:]
            # print(f"After getting clear the history: {history}\n")

            for message in stored_messages:
                history.add_message(message)

            # print(f"After adding the history in the database: {history}\n")

        logger.info(f"Remaining History: {history}")

        return history

    except Exception as e:
        raise Exception(f"Exception has been occurred in the get_session_history_with_sql_chat_history function: {e}")


# Retrieve session history using in-memory chat history
def get_session_history_with_chat_messages_history(session_id: int) -> BaseChatMessageHistory:
    history = conversation_history.setdefault(session_id, ChatMessageHistory())
    stored_messages = history.messages

    if len(stored_messages) > MAINTAIN_CONVERSATION_HISTORY_COUNT:
        history.clear()
        stored_messages = stored_messages[-MAINTAIN_CONVERSATION_HISTORY_COUNT:]

    for message in stored_messages:
        history.add_message(message)

    logger.info(f"History: {history}")
    return history