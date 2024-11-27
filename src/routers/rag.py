"""
Work In Progress, not mounted in API routes.
"""
import json
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from src.core.knowledge import Collection, Store

rag_router = APIRouter()
# temporarily make store variable
store: Store | None = None


@rag_router.get('/collections/list')
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


@rag_router.post('/collections/new')
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


@rag_router.post('/collections/upload')
async def upload_document():
    """Uploads a document to an existing collection."""
    # TODO: file vs ?
