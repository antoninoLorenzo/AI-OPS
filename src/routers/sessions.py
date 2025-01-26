"""
### Session routes
**Session Management**
- [x] GET    /sessions                    # (list) List all conversations
- [x] POST   /sessions                    # (new) Create new conversation
- [x] PUT    /sessions/{sid}              # (rename) Change session name
- [x] DELETE /sessions/{sid}              # (delete) Delete conversation
- [x] GET    /sessions/{sid}/chat         # Get the conversation with the agent
- [x] PUT    /sessions/{sid}/chat         # save the conversation
**Agent**
- [x] POST   /sessions/{sid}/chat         # Make a query to the agent
"""
import json

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.agent import Agent
from src.dependencies import get_agent

session_router = APIRouter()


@session_router.get('/sessions')
async def list_sessions(agent: Agent = Depends(get_agent)):
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


@session_router.get('/sessions/{sid}/chat')
async def get_session(sid: int, agent: Agent = Depends(get_agent)):
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
        'messages': session.model_dump()
    }


@session_router.post('/sessions')
async def new_session(name: str, agent: Agent = Depends(get_agent)):
    """
    Creates a new session.
    Returns the new session id.
    """
    sessions = agent.get_sessions()

    if len(sessions) == 0:
        new_id = 1
    else:
        new_id = max(sorted(sessions.keys())) + 1
    agent.new_session(new_id, name)
    # agent.get_session(new_id).name = name

    return {'sid': new_id}


@session_router.put('/sessions/{sid}')
async def rename_session(sid: int, new_name: str, agent: Agent = Depends(get_agent)):
    """Rename a session."""
    agent.rename_session(sid, new_name)


@session_router.put('/sessions/{sid}/chat')
async def save_session(sid: int, agent: Agent = Depends(get_agent)):
    """
    Save a session.
    Returns JSON response with 'success' (True or False) and 'message'.
    """
    try:
        agent.save_session(sid)
        return {'success': True, 'message': f'Saved session {sid}'}
    except ValueError as err:
        return {'success': False, 'message': err}


@session_router.delete('/sessions/{sid}')
async def delete_session(sid: int, agent: Agent = Depends(get_agent)):
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
        # TODO: inject Prometheus Metric to measure token consumption
        yield from agent.query(sid, usr_query)
    except Exception as err:
        yield json.dumps({'error': f'query_generator: {err}'})
        raise RuntimeError from err


@session_router.post('/sessions/{sid}/chat')
async def query(sid: int, body: dict = Body(...), agent: Agent = Depends(get_agent)):
    """Makes a query to the Agent in the current session context;
    returns the stream for the response using `query_generator`.
    :param agent:
    :param sid: session id
    :param body: the request body (contains the query string)"""
    usr_query = body.get("query")
    if not usr_query:
        raise HTTPException(status_code=400, detail="Query parameter required")
    return StreamingResponse(query_generator(agent, sid, usr_query))
