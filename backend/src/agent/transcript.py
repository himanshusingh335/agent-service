import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

transcript_logger = logging.getLogger("task-agent")


def log_message(message: BaseMessage) -> None:
    text = str(message.text)
    if isinstance(message, HumanMessage):
        transcript_logger.info(text, extra={"role": "human", "content": text})
    elif isinstance(message, AIMessage):
        extra = {"role": "ai", "content": text}
        if message.tool_calls:
            extra["tool_calls"] = [
                {"name": tc["name"], "args": tc["args"]} for tc in message.tool_calls
            ]
        transcript_logger.info(text, extra=extra)
    elif isinstance(message, ToolMessage):
        transcript_logger.info(
            text,
            extra={"role": "tool", "tool_name": message.name, "content": text},
        )


def log_new_messages(messages: list[BaseMessage], prev_len: int) -> None:
    for message in messages[prev_len:]:
        log_message(message)
