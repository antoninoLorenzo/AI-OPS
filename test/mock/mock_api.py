from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import StreamingResponse

from src.core.memory.schema import Conversation, Message, Role

app = FastAPI()
conversation_counter = 0


@app.get('/ping')
def ping():
    return status.HTTP_200_OK


@app.get('/conversations')
async def list_conversations() -> list:
    global conversation_counter
    conversation_counter += 1
    return [
        Conversation(
            conversation_id=conversation_counter,
            name='untitled',
            messages=[Message(role=Role.USER, content='Hi')]
        )
    ]


@app.post('/conversations')
async def new_conversation(name: str) -> Conversation:
    global conversation_counter
    conversation_counter += 1
    return Conversation(
        conversation_id=conversation_counter,
        name=name,
        messages=[Message(role=Role.USER, content='Hi')]
    )


@app.get('/conversations/{conversation_id}')
async def get_conversation(conversation_id: int) -> Conversation:
    if conversation_id < 0:
        raise HTTPException(status_code=400, detail='invalid conversation id')
    
    return Conversation(
        conversation_id=conversation_id,
        name='untitled',
        messages=[Message(role=Role.USER, content='Hi')]
    )


@app.post('/conversations/{conversation_id}')
async def rename_conversation(conversation_id: int, new_name: str):
    if len(new_name) == 0:
        raise HTTPException(status_code=400, detail='invalid value for new_name')
    if conversation_id < 0:
        raise HTTPException(status_code=404, detail='conversation not found')
    
    return Conversation(
        conversation_id=conversation_id,
        name=new_name,
        messages=[Message(role=Role.USER, content='Hi')]
    )


@app.put('/conversations/{conversation_id}')
async def save_conversation(conversation_id: int):
    pass


@app.delete('/conversations/{conversation_id}')
async def delete_conversation(conversation_id: int):
    pass


def query_generator(conversation_id: int, usr_query: str):
    import time
    response = f'\n# Conversation **{conversation_id}**\nResponse for: *{usr_query}*'
    for c in response:
        time.sleep(0.1)
        yield c


@app.post('/conversations/{conversation_id}/chat')
async def query(conversation_id: int, body: dict = Body(...)):
    usr_query = body.get("message")
    if not usr_query:
        raise HTTPException(status_code=400, detail="Required 'message' parameter.")
    return StreamingResponse(query_generator(conversation_id, usr_query))



