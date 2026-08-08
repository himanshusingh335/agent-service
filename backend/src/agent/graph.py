from langchain.agents import create_agent
from langchain_openrouter import ChatOpenRouter

from agent.mcp import load_mcp_tools
from agent.middleware import build_human_in_the_loop_middleware, build_summarization_middleware
from agent.tools import get_current_date
from core.config import settings

LOCAL_TOOLS = [get_current_date]

SYSTEM_PROMPT = (
    "You are a concise, friendly task-management assistant. "
    "Use the available tools to add and remove tasks for the user.\n"
    "1. Brevity: keep responses short and confirm actions plainly.\n"
    "2. Required parameters: before calling ANY tool, check its schema and make sure every required "
    "parameter is included in the call. If you genuinely cannot determine a required value, ask the "
    "user for it rather than calling the tool without it."
)

async def build_agent(checkpointer):
    model = ChatOpenRouter(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        temperature=0,
        reasoning={"effort": "medium"},
    )

    mcp_tools = await load_mcp_tools()
    tools = [*LOCAL_TOOLS, *mcp_tools]

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[build_summarization_middleware(model), build_human_in_the_loop_middleware()],
        checkpointer=checkpointer,
    )
