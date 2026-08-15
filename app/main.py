from fastapi.middleware.cors import CORSMiddleware
import uvicorn, torch, gc, json
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Depends
from settings.setting import *
from services.auth_manager import Manager
from utilities.utils import log_requests
from api.api_v1.api import router
from logs.logger_setup import setup_logger


device = torch.device('cuda')
gc.collect()
torch.cuda.empty_cache()

app_logger = setup_logger("app_logger")

# define fastapi app
app = FastAPI()

# # Load config
# with open("config/config_env.json") as f:
#     config = json.load(f)
#
# USE_STATIC = config.get("USE_STATIC", False)
# USE_TEMPLATES = config.get("USE_TEMPLATES", False)
#
# if USE_STATIC:
#     print("Including static files in execution...")
#     # Add logic to use static files
#
# if USE_TEMPLATES:
#     print("Including templates in execution...")
#     # Add logic to use templates


app.mount("/static", StaticFiles(directory="./static"), name="static")

# Include API Router
app.include_router(router)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#app.middleware("http")(log_requests)

if __name__ == "__main__":
    try:
        app_logger.info("Server Init started")
        manager = Manager()
        app_logger.info(f"Manager assigned {SERVER_IP_ADDRESS} {SERVER_PORT_ADDRESS}")
        uvicorn.run(app, host=SERVER_IP_ADDRESS, port=SERVER_PORT_ADDRESS, log_level="debug", reload=False, reload_includes=["*.html", "*.js"])
        app_logger.info("Manager's Server Started Successfully")
    except Exception as ex:
        app_logger.exception("Exception in main {}".format(ex))
    finally:
        app_logger.info("Server is closing")
