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
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic_settings import BaseSettings
from tool_parse import ToolRegistry

from src import initialize_knowledge
from src.agent import Agent
from src.agent.knowledge import Store
from src.agent.llm import ProviderError
from src.agent.plan import TaskStatus
from src.agent.tools import TOOLS

load_dotenv()
TR = ToolRegistry()


# --- Get AI-OPS Settings
class AgentSettings(BaseSettings):
    """Setup for AI Agent"""
    MODEL: str = os.environ.get('MODEL', 'gemma2:9b')
    ENDPOINT: str = os.environ.get('ENDPOINT', 'http://localhost:11434')
    PROVIDER: str = os.environ.get('PROVIDER', 'ollama')
    PROVIDER_KEY: str = os.environ.get('PROVIDER_KEY', '')
    USE_RAG: bool = os.environ.get('USE_RAG', False)


class RAGSettings(BaseSettings):
    """Settings for Qdrant vector database"""
    RAG_URL: str = os.environ.get('RAG_URL', 'http://localhost:6333')
    IN_MEMORY: bool = os.environ.get('IN_MEMORY', True)
    EMBEDDING_MODEL: str = os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
    # There the assumption that embedding url is the same of llm provider
    EMBEDDING_URL: str = os.environ.get('ENDPOINT', 'http://localhost:11434')


class APISettings(BaseSettings):
    """Setup for API"""
    ORIGINS: list = [
        # '*',  # development only
        'http://localhost:3000'  # default frontend port
    ]


agent_settings = AgentSettings()
api_settings = APISettings()


# --- Initialize RAG
if agent_settings.USE_RAG:
    rag_settings = RAGSettings()

    store = Store(
        str(Path(Path.home() / '.aiops')),
        url=rag_settings.RAG_URL,
        embedding_url=rag_settings.EMBEDDING_URL,
        embedding_model=rag_settings.EMBEDDING_MODEL,
        in_memory=rag_settings.IN_MEMORY
    )

    initialize_knowledge(store)
    available_documents = ''
    for cname, coll in store.collections.items():
        doc_topics = ", ".join([topic.name for topic in coll.topics])
        available_documents += f"- '{cname}': {doc_topics}\n"


    @TR.register(
        description=f"""Search documents in the RAG Vector Database.
        Available collections are:
        {available_documents}
        """
    )
    def search_rag(rag_query: str, collection: str) -> str:
        """
        :param rag_query: what should be searched
        :param collection: the collection name
        """
        return '\n\n'.join(store.retrieve_from(rag_query, collection))


# --- Initialize Agent
agent = Agent(
    model=agent_settings.MODEL,
    llm_endpoint=agent_settings.ENDPOINT,
    tools_docs='\n'.join([tool.get_documentation() for tool in TOOLS]),
    provider=agent_settings.PROVIDER,
    provider_key=agent_settings.PROVIDER_KEY,
    tool_registry=TR
)

# --- Initialize API
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def ping():
    """Used to check if API is online on CLI startup"""
    return ''


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
    agent.get_session(new_id).name = name

    return {'sid': new_id}


@app.get('/session/{sid}/rename/')
def rename_session(sid: int, new_name: str):
    """Rename a session."""
    agent.rename_session(sid, new_name)  


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

def query_generator(sid: int, usr_query: str):
    """Generator function for `/session/{sid}/query endpoint`;
    yields Agent response chunks or error.
    :param sid: session id
    :param usr_query: query string"""
    try:
        stream = agent.query(sid, usr_query)
        yield from stream
    except ProviderError as err:
        yield json.dumps({'error': str(err)})


@app.post('/session/{sid}/query/')
def query(sid: int, body: dict = Body(...)):
    """Makes a query to the Agent in the current session context;
    returns the stream for the response using `query_generator`.
    :param sid: session id
    :param body: the request body (contains the query string)"""
    usr_query = body.get("query")
    if not usr_query:
        raise HTTPException(status_code=400, detail="Query parameter required")
    return StreamingResponse(query_generator(sid, usr_query))


# --- PLAN RELATED
@app.get('/session/{sid}/plan/list')
def list_plans(sid: int):
    """
    Return all Plans.
    Returns the JSON representation of all Plans in the current Session.
    """
    session = agent.get_session(sid)
    plans = {}

    if session is None:
        return {"error": "No session found"}
    if session.plans is None or len(session.plans) == 0:
        return {"error": "No plans available"}

    for i, plan in enumerate(session.plans):
        tasks = []
        for task in plan.tasks:
            tasks.append({
                'thought': task.thought,
                'command': task.command,
                'output': task.output
            })
        plans[i] = tasks
    return plans


def execute_plan_stream(sid: int):
    """Generator for plan execution and status updates"""
    execution = agent.execute_plan(sid)
    for iteration in execution:
        for task in iteration:
            if task.status == TaskStatus.DONE:
                task_str = f'ai-ops:~$ {task.command}\n{task.output}\n'
                yield task_str

    plan = agent.mem.get_plan(sid)
    if plan:
        eval_results = 'Task Results:\n'
        for task in plan.plan_to_dict_list():
            eval_results += f'{task["command"]}\n{task["output"]}\n\n'

        yield from query_generator(sid, eval_results)
    else:
        yield "No plans available"


@app.get('/session/{sid}/plan/execute')
def execute_plan(sid: int):
    """
    Executes last plan.
    Returns a stream that provide status for plan tasks execution.
    """
    return StreamingResponse(execute_plan_stream(sid))


# --- KNOWLEDGE RELATED
@app.get('/collections/list')
def list_collections():
    """
    Returns available Collections.
    Returns a JSON list of available Collections.
    """
    available_collections = [c.to_dict() for c in store.collections.values()]
    return available_collections


@app.post('collections/new')
def create_collection(title: str, base_path: str, topics: list):
    """
    Creates a new Collection.
    :param title: unique collection title
    :param base_path: local path to collection json file
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
    # TODO:
    #  when a new collection is uploaded the search_rag tool
    #  should be re-registered and the agent should be updated
