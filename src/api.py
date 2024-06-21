"""
API Interface for AI-OPS, here is provided the list of available endpoints.

Session Related:
- /session/list: Return all sessions.
- /session/get/{sid}: Return a specific session by ID.
- /session/new/{name}: Creates a new session.
- /session/{sid}/rename/{new_name}: Rename a session.
- /session/{sid}/save: Save a session.
- /session/{sid}/delete: Delete a session.

Agent Related:
- /session/{sid}/query/{q}: Makes a query to the Agent.

Plan Related:
- /session/{sid}/plan/list: Return all Plans in the current Session.
- /session/{sid}/plan/execute: Executes the last plan.

Knowledge Related:
- /collections/list: Returns available Collections.
- /collections/new: Creates a new Collection.
"""
import argparse
from argparse import ArgumentParser

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse


from src import upload_knowledge
from src.agent import Agent
from src.agent.llm import LLM
from src.agent.knowledge import Store
from src.agent.tools import TOOLS

# Agent Setup
# model = 'llama3'
# tools = '\n'.join([tool.get_documentation() for tool in TOOLS])
model = 'gemma:2b'  # testing setup
tools = ''
# store = Store()
# upload_knowledge('../data/json', store)
agent = Agent(model=model, tools_docs=tools)# , knowledge_base=store)

# API Setup
origins = [
    'http://localhost:3000'  # default frontend port
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- SESSION RELATED
@app.get('/session/list')
def list_sessions():
    """
    Return all sessions.
    Returns a JSON list of Session objects.
    """
    sessions = agent.get_sessions()
    json_sessions = []
    for sid, session in sessions.items():
        json_sessions.append({
            'sid': sid,
            'name': session.name,
            'messages': session.messages_to_dict_list(),
            # '': session.plans
        })
    return json_sessions


@app.get('/session/get/')
def get_session(sid: int):
    """
    Return a specific session by id.
    Returns JSON representation for a Session object.

    If session do not exist returns JSON response:
        {'success': False, 'message': 'error message'}
    """
    session = agent.get_session(sid)
    if not session:
        return {'success': False, 'message': 'Invalid session id'}
    return {
        'sid': sid,
        'name': session.name,
        'messages': session.messages_to_dict_list()
    }


@app.get('/session/new/')
def new_session(name: str):
    """
    Creates a new session.
    Returns the new session id.
    """
    sessions = agent.get_sessions()

    if len(sessions) == 0:
        new_id = 1
    else:
        new_id = max(sorted(sessions.keys())) + 1
    agent.new_session(new_id)

    return {'sid': new_id}


@app.get('/session/{sid}/rename/')
def rename_session(sid: int, new_name: str):
    """Rename a session."""
    agent.rename_session(sid, new_name)  # should return a page reload signal?


@app.get('/session/{sid}/save/')
def save_session(sid: int):
    """
    Save a session.
    Returns JSON response with 'success' (True or False) and 'message'.
    """
    try:
        agent.save_session(sid)
        return {'success': True, 'message': f'Saved session {sid}'}
    except ValueError as err:
        return {'success': False, 'message': err}


@app.get('/session/{sid}/delete/')
def delete_session(sid: int):
    """
    Delete a session.
    Returns JSON response with 'success' (True or False) and 'message'.
    """
    try:
        agent.delete_session(sid)
        return {'success': True, 'message': f'Deleted session {sid}'}
    except ValueError as err:
        return {'success': False, 'message': err}


# --- AGENT RELATED

def query_generator(sid: int, q: str):
    # testing with llm only
    stream = agent.query(sid, q, rag=False)
    for chunk in stream:
        yield chunk


@app.get('/session/{sid}/query/')
def query(sid: int, q: str):
    """
    Makes a query to the Agent.
    Returns the stream for the response.
    """
    return StreamingResponse(query_generator(sid, q))


# --- PLAN RELATED
@app.get('/session/{sid}/plan/list')
def list_plans(sid: int):
    """
    Return all Plans.
    Returns the JSON representation of all Plans in the current Session.
    """


@app.get('/session/{sid}/plan/execute')
def execute_plan(sid: int):
    """
    Executes last plan.
    Returns a stream that provide status for plan tasks execution.
    """


# --- KNOWLEDGE RELATED
@app.get('collections/list')
def list_collections():
    """
    Returns available Collections.
    Returns a JSON list of available Collections.
    """


@app.post('collections/new')
def create_collection(title: str, base_path: str, topics: list):
    """
    Creates a new Collection.
    :param title: unique collection title
    :param base_path: the local path to the json file containing the collection dataset
    :param topics: a list of collection topics

    Returns a stream to notify progress if input is valid.

    Returns error message for any validation error.
    1. title should be unique
    2. base_path should exist and be a json file
    3. the json file should follow this format:
    [
        {
            "title": "collection title",
            "content": "...",
            "category": "document topic"
        },
        ...
    ]
    """


if __name__ == "__main__":
    # get api settings ...
    pass
