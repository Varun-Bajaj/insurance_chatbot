from settings.setting import *
from logs.logger_setup import *
from services.Text2SQL_Manager import *

# if CHATBOT_TYPE == "mos":
#     from .mos_chatbot_manager import ModelManager
# elif CHATBOT_TYPE == "billrMD":
#     from .billrMD_chatbot_manager import ModelManager
# elif CHATBOT_TYPE == "ims":
#     from .ims_chatbot_manager import ModelManager
# else:
#     raise ValueError(f"Unsupported chatbot type: {CHATBOT_TYPE}")


app_logger = setup_logger("app_logger")


## Define models
# list_model_for_each_worker = {
#     0: LLM_MODEL_NAME,
# }
# ## Map embedding models
# list_embedding_model_for_llm_models = {
#     0: EMBEDDING_MODEL_NAME,
# }
# model_pool = [ModelManager(model_id=i, model_name=list_model_for_each_worker[0],
#                            embedding_model=list_embedding_model_for_llm_models[0]) for i in
#               range(NUMBER_OF_MODEL_PIPELINE)]


# async def get_free_model():
#     """Find a free model in the model pool."""
#     for model in model_pool:
#         if not model.is_busy:
#             return model
#     return None  # All models are busy


# Function to handle query and stream the response
async def handle_query(user_id, session_id, query_id, db):
    try:
        print("inside handle_query")
        # app_logger.info("inside handle_query")
        # Process the query with the free model
        # response = await model.process_query(user_id, query_id)
        response = await process_query_with_guardrails(user_id, session_id, query_id, db)
        # Send the response back to the client
        # await websocket.send_text(response)
        return response

    except Exception as e:
        print(f"Error processing query: {e}\n\n")
        app_logger.exception(f"Error processing query: {e}")

