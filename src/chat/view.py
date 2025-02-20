"""
Chat Endpoints:

- `GET /conversation`                         : load conversations
- `POST /conversation`                        : create conversation
- `GET /conversation/<conversation_id>`       : get conversation
- `POST /conversation/<conversation_id>`      : rename conversation
- `PUT /conversation/<conversation_id>`       : save conversation
- `DELETE /conversation/<conversation_id>`    : delete conversation
- `POST /conversation/<conversation_id>/chat` : stream response for message
"""
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.agent import Agent
from src.chat.service import (ConversationService, get_agent,
                              get_conversation_service, query_generator)
from src.core import Conversation, Message, Role

router = APIRouter(prefix='/conversations')


@router.get('')
async def list_conversations(
        conversation_service: ConversationService = Depends(get_conversation_service)
) -> List[Conversation]:
    return conversation_service.load_conversations()


@router.post('')
async def new_conversation(
        name: str,
        conversation_service: ConversationService = Depends(get_conversation_service)
) -> Conversation:
    return conversation_service.new_conversation(name)


@router.get('/{conversation_id}')
async def get_conversation(
        conversation_id: int,
        conversation_service: ConversationService = Depends(get_conversation_service)
) -> Conversation:
    return conversation_service.get_conversation(conversation_id)


@router.post('/{conversation_id}')
async def rename_conversation(
        conversation_id: int, new_name: str,
        conversation_service: ConversationService = Depends(get_conversation_service)
) -> Conversation:
    return conversation_service.rename_conversation(conversation_id, new_name)


@router.put('/{conversation_id}')
async def save_conversation(
        conversation_id: int,
        conversation_service: ConversationService = Depends(get_conversation_service)
):
    conversation_service.save_conversation(conversation_id)


@router.delete('/{conversation_id}')
async def delete_conversation(
        conversation_id: int,
        conversation_service: ConversationService = Depends(get_conversation_service)
):
    conversation_service.delete_conversation(conversation_id)


@router.post('/{conversation_id}/chat')
async def query(
        conversation_id: int,
        body: dict = Body(...),
        agent: Agent = Depends(get_agent),
        conversation_service: ConversationService = Depends(get_conversation_service)
):
    usr_query = body.get("query")
    if not usr_query:
        raise HTTPException(status_code=400, detail="Query parameter required")

    conversation = conversation_service.get_conversation(conversation_id)
    conversation += Message(role=Role.USER, content=usr_query)

    return StreamingResponse(query_generator(agent, conversation))
