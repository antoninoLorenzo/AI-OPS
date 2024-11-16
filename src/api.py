"""
API Interface for AI-OPS, here is provided the list of available endpoints.
# TODO: dependency injection of Agent
# TODO: separate routes

Session routes:
- Agent
    - /session/{sid}/query/{q}         : Makes a query to the Agent.
- Memory Management
    - /session/list                    : Return all sessions.
    - /session/get/{sid}               : Return a specific session by ID.
    - /session/new/{name}              : Creates a new session.
    - /session/{sid}/rename/{new_name} : Rename a session.
    - /session/{sid}/save              : Save a session.
    - /session/{sid}/delete            : Delete a session.

# TODO: refactor session routes to be REST compliant
    **Session Management**
    - GET    /sessions                    # (list) List all conversations
    - POST   /sessions                    # (new) Create new conversation
    - PUT    /sessions/{sid}              # (rename) Change session name
    - DELETE /sessions/{sid}              # (delete) Delete conversation
    - GET    /sessions/{sid}/chat         # Get the conversation with the agent
    **Agent**
    - POST   /sessions/{sid}/chat         # Make a query to the agent

RAG Routes:
- /collections/list    : Returns available Collections.
- /collections/new     : Creates a new Collection.
- /collections/upload/ : Upload document to an existing Collection
"""
import json
from typing import Optional

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Form, File, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.config import API_SETTINGS
from src.dependencies import get_agent
from src.agent import Agent
from src.core.knowledge import Collection

load_dotenv()

# TODO: re-integrate RAG
# temporarily make store variable
store = None

# --- Initialize API
# TODO: implement proper CORS
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=API_SETTINGS.ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def ping():
    """Used to check if API is online on CLI startup"""
    # TODO: use /ping an return Status.OK
    # could also consider using /health and adding more functionality
    return ''


# --- SESSION RELATED
@app.get('/session/list')
def list_sessions(agent: Agent = Depends(get_agent)):
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
            'messages': session.messages,
            # '': session.plans
        })
    return json_sessions


@app.get('/session/get/')
def get_session(sid: int, agent: Agent = Depends(get_agent)):
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
        'messages': session.message_dict
    }


@app.get('/session/new/')
def new_session(name: str, agent: Agent = Depends(get_agent)):
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
def rename_session(sid: int, new_name: str, agent: Agent = Depends(get_agent)):
    """Rename a session."""
    agent.rename_session(sid, new_name)


@app.get('/session/{sid}/save/')
def save_session(sid: int, agent: Agent = Depends(get_agent)):
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
def delete_session(sid: int, agent: Agent = Depends(get_agent)):
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

def query_generator(agent: Agent, sid: int, usr_query: str):
    """Generator function for `/session/{sid}/query endpoint`;
    yields Agent response chunks or error.
    :param agent:
    :param sid: session id
    :param usr_query: query string"""
    try:
        yield from agent.query(sid, usr_query)
    except Exception as err:
        yield json.dumps({'error': f'query_generator: {err}'})


@app.post('/session/{sid}/query/')
def query(sid: int, body: dict = Body(...), agent: Agent = Depends(get_agent)):
    """Makes a query to the Agent in the current session context;
    returns the stream for the response using `query_generator`.
    :param agent:
    :param sid: session id
    :param body: the request body (contains the query string)"""
    usr_query = body.get("query")
    if not usr_query:
        raise HTTPException(status_code=400, detail="Query parameter required")
    return StreamingResponse(query_generator(agent, sid, usr_query))


# --- RAG RELATED
@app.get('/collections/list')
def list_collections():
    """
    Returns available Collections.
    Returns a JSON list of available Collections.
    """
    if store:
        available_collections = [c.to_dict() for c in store.collections.values()]
        return available_collections
    else:
        return {}


@app.post('/collections/new')
async def create_collection(
        title: str = Form(...),
        file: Optional[UploadFile] = File(None)
):
    """
    Creates a new Collection.
    :param file: uploaded file
    :param title: unique collection title

    Returns error message for any validation error.
    1. title should be unique
    2. the file should follow this format:
    [
        {
            "title": "collection title",
            "content": "...",
            "category": "document topic"
        },
        ...
    ]

    (TODO) Returns a stream to notify progress if input is valid.
    (TODO)
      when a new collection is uploaded the search_rag tool
      should be re-registered and the agent should be updated
    """
    if not store:
        return {'error': "RAG is not available"}
    if title in list(store.collections.keys()):
        return {'error': f'A collection named "{title}" already exists.'}

    if not file:
        available_collections = list(store.collections.values())
        last_id = available_collections[-1].collection_id \
            if available_collections \
            else 0
        store.create_collection(
            Collection(
                collection_id=last_id + 1,
                title=title,
                documents=[],
                topics=[]
            )
        )
    else:
        if not file.filename.endswith('.json'):
            return {'error': 'Invalid file'}

        contents = await file.read()
        try:
            collection_data: list[dict] = json.loads(contents.decode('utf-8'))
        except (json.decoder.JSONDecodeError, UnicodeDecodeError):
            return {'error': 'Invalid file'}

        try:
            new_collection = Collection.from_dict(title, collection_data)
        except ValueError as schema_err:
            return {'error': schema_err}

        try:
            store.create_collection(new_collection)
        except RuntimeError as create_err:
            return {'error': create_err}

    return {'success': f'{title} created successfully.'}


@app.post('/collections/upload')
async def upload_document():
    """Uploads a document to an existing collection."""
    # TODO: file vs ?
