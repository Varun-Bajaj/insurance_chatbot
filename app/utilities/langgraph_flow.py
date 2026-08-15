from services.CRMChatbotFlow import CRMChatbotManager
from services.CRMChatbotGraphFlow import GraphAgentChatbotManager
from settings.setting import *

if APPROACH == 1:
    manager = CRMChatbotManager()

else:
    manager = GraphAgentChatbotManager()

from IPython.display import Image, display

async def show():
    graph = await manager.create_sql_agent()
    ascii_diagram = graph.get_graph().draw_ascii()
    print(ascii_diagram)
    # graph = await manager.create_sql_agent()
    # display(Image(graph.get_graph().draw_mermaid_png()))
