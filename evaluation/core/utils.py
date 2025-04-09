import hashlib
from itertools import pairwise
from typing import Any, Dict, List, Union

from deepeval.metrics import BaseConversationalMetric, BaseMetric
from deepeval.test_case import ConversationalTestCase, LLMTestCase

from src.core import Conversation, Message, Role
from src.utils import get_logger

LOGGER =  get_logger(__file__)


def conversation_to_test_case(
    conversation: Conversation,
    context: List[str] | None = None,
    chatbot_role: str | None = None
) -> LLMTestCase | ConversationalTestCase:
    """
    Handle conversion from AI-OPS Conversation to DeepEval LLMTestCase or ConversationTestCase.

    Note: conversion is designed to work for: KnowledgeRetention, RoleAdherence and Hallucination 
    metrics, other metrics require additional data (expected output, tools called etc.)

    :param conversation: a conversation with AI-OPS Assistant

    :return: a LLMTestCase if the Conversation contains one user message and one assistant message
            , otherwise a ConversationalTestCase.
    """
    messages = conversation.messages

    # system prompt is not generally part of a Test Case for deepeval metrics
    if messages[0].role == Role.SYS:
        messages = messages[1:]
    
    # the conversation is composed of a user request and an assistant response
    if len(messages) == 2:    
        # verify user and assistant message alternate
        valid_format = messages[0].role == Role.USER and \
            messages[1].role == Role.ASSISTANT
        if not valid_format:
            msg = (
                f'expected user and assistant message, got: {messages}'
            )
            LOGGER.error(msg)
            raise ValueError(msg)

        return LLMTestCase(
            input=messages[0].content,
            actual_output=messages[1].content,
            context=context
        )

    turns = []
    for user_message, assistant_message in pairwise(messages):
        # verify user and assistant message alternate
        valid_format = user_message.role == Role.USER and \
            assistant_message.role == Role.ASSISTANT
        if not valid_format:
            msg = (
                f'expected user and assistant message, got: {messages}'
            )
            LOGGER.error(msg)
            raise ValueError(msg)

        turns.append(
            LLMTestCase(
                input=user_message.content,
                actual_output=assistant_message.content
            )
        )

    return ConversationalTestCase(
        turns=turns, 
        chatbot_role=chatbot_role
    )


def gen_checkpoint_id(
    architecture: str, 
    model: str, 
    conversation_name: str, 
    conversation_type: str
):
    m = hashlib.sha1()
    raw = f'{conversation_name}_{architecture}-{model}_{conversation_type}'
    m.update(raw.encode())
    return m.hexdigest()


def verify_checkpoint_id(
    architecture: str, 
    model: str, 
    conversation_name: str, 
    conversation_type: str, 
    hash: str
):
    h = gen_checkpoint_id(architecture, model, conversation_name, conversation_type)
    return h == hash
    
