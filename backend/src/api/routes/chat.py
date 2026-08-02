from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from agent.transcript import log_new_messages
from api.deps import get_agent
from api.schemas import ChatRequest, ChatResponse
from core.logging import session_id_var

router = APIRouter(prefix="/chat", tags=["chat"])


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _inputs(message: str) -> dict:
    return {"messages": [{"role": "user", "content": message}]}


@router.post("/invoke", response_model=ChatResponse)
async def invoke(request: ChatRequest, agent=Depends(get_agent)):
    token = session_id_var.set(request.session_id)
    try:
        config = _config(request.session_id)
        state = await agent.aget_state(config)
        prev_len = len(state.values.get("messages", []))

        result = await agent.ainvoke(_inputs(request.message), config=config)

        log_new_messages(result["messages"], prev_len)
        reply = str(result["messages"][-1].text)
        return ChatResponse(session_id=request.session_id, reply=reply)
    finally:
        session_id_var.reset(token)


@router.post("/stream")
async def stream(request: ChatRequest, agent=Depends(get_agent)):
    async def event_generator():
        ctx_token = session_id_var.set(request.session_id)
        try:
            config = _config(request.session_id)
            state = await agent.aget_state(config)
            prev_len = len(state.values.get("messages", []))

            run_stream = await agent.astream_events(
                _inputs(request.message), config=config, version="v3"
            )
            async for message in run_stream.messages:
                async for text_delta in message.text:
                    if text_delta:
                        yield {"data": text_delta}

            final_state = await agent.aget_state(config)
            log_new_messages(final_state.values.get("messages", []), prev_len)
        finally:
            session_id_var.reset(ctx_token)

    return EventSourceResponse(event_generator())
