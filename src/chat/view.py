from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.agent import Agent
from src.core import Conversation
from src.dependencies import get_agent
from src.chat.service import ConversationService, get_conversation_service

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


def query_generator(conversation_id: int, usr_query: str):
    import time
    response = f'\n# Conversation **{conversation_id}**\nResponse for: *{usr_query}*'
    for c in response:
        time.sleep(0.1)
        yield c


@router.post('/{conversation_id}/chat')
async def query(
        conversation_id: int,
        body: dict = Body(...),
        agent: Agent = Depends(get_agent),
        conversation_service: ConversationService = Depends(get_conversation_service)
):
    pass
