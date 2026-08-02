from langchain.agents import create_agent
from langchain_groq import ChatGroq

from agent.mcp import load_mcp_tools
from agent.middleware import build_summarization_middleware
from agent.tools import get_current_date
from core.config import settings

LOCAL_TOOLS = [get_current_date]

SYSTEM_PROMPT=(
    "You are Penny, a concise and friendly personal budget assistant. "
    "Use the available tools to answer questions about the user's budgets and transactions. "
    "Formatting rules you must always follow:\n"
    "1. Currency: always prefix amounts with ₹ and no other symbol. Never use 'INR' or 'Rs'.\n"
    "2. Number formatting: use Indian-style comma grouping (e.g. ₹1,23,456.00 not ₹123,456.00).\n"
    "3. Structure: present any comparison, breakdown, or multi-item answer as a plain-text table "
    "using aligned columns. Use a table even for two rows if there are multiple fields.\n"
    "4. Brevity: keep prose to one sentence max; let the table carry the detail.\n"
    "5. Auto-categorisation: if the user asks to add a transaction without specifying a category, "
    "call the classify_description tool with the transaction description to predict the category "
    "automatically, then proceed with adding the transaction using the predicted category."
)

async def build_agent(checkpointer):
    model = ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key)

    mcp_tools = await load_mcp_tools()
    tools = [*LOCAL_TOOLS, *mcp_tools]

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[build_summarization_middleware(model)],
        checkpointer=checkpointer,
    )
