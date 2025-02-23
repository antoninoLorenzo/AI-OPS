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
    conversation = conversation_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=400, detail='invalid conversation id')
    return conversation


@router.post('/{conversation_id}')
async def rename_conversation(
        conversation_id: int, new_name: str,
        conversation_service: ConversationService = Depends(get_conversation_service)
) -> Conversation:
    if len(new_name) == 0:
        raise HTTPException(status_code=400, detail='invalid value for new_name')
    
    renamed = conversation_service.rename_conversation(conversation_id, new_name)
    if not renamed:
        raise HTTPException(status_code=404, detail='conversation not found')
    return renamed


@router.put('/{conversation_id}')
async def save_conversation(
        conversation_id: int,
        conversation_service: ConversationService = Depends(get_conversation_service)
):
    if not conversation_service.save_conversation(conversation_id):
        raise HTTPException(status_code=400, detail='failed saving conversation')


@router.delete('/{conversation_id}')
async def delete_conversation(
        conversation_id: int,
        conversation_service: ConversationService = Depends(get_conversation_service)
):
    if not conversation_service.delete_conversation(conversation_id):
        raise HTTPException(status_code=400, detail='failed deleting conversation')


@router.post('/{conversation_id}/chat')
async def query(
        conversation_id: int,
        body: dict = Body(...),
        agent: Agent = Depends(get_agent),
        conversation_service: ConversationService = Depends(get_conversation_service)
):
    usr_query = body.get("query")
    if not usr_query or not isinstance(usr_query, str) or len(usr_query) == 0:
        raise HTTPException(status_code=400, detail='expected {"query": str}')

    conversation = conversation_service.get_conversation(conversation_id)
    conversation += Message(role=Role.USER, content=usr_query)

    return StreamingResponse(query_generator(agent, conversation))
