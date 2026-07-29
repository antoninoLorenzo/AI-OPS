import sys
from typing import Annotated

from fastapi import Depends, Request, HTTPException, status
from fastapi.security import APIKeyHeader

from ai_ops.api.config import get_settings


API_KEY_NAME = "X-AI-OPS-ApiKey"
api_key_header = APIKeyHeader(name=API_KEY_NAME)
handle_api_key = None

async def _handle_api_key(req: Request, api_key: Annotated[APIKeyHeader, Depends(api_key_header)]):
    api_settings = get_settings()
    if api_key != api_settings.auth_token.get_secret_value():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


# NOTE: must take no parameters. FastAPI introspects a dependency's signature,
# so `*args, **kwargs` would be turned into required `args`/`kwargs` query
# parameters on every guarded route (making the whole API 422 in no-auth mode).
async def _handle_no_op():
    pass


def setup_auth():
    global handle_api_key

    # rather than making the check everytime handle_api_key is called we bind 
    # the correct strategy at startup.
    api_settings = get_settings()

    is_local_api = api_settings.host in ('127.0.0.1', 'localhost')
    if api_settings.auth_token is not None:
        handle_api_key = _handle_api_key
    else:
        if is_local_api:
            print("WARNING: AI_OPS_AUTH_TOKEN is not set")
            handle_api_key = _handle_no_op
        else:
            # security policy is never allow deployment without token if exposed on 
            # the network.
            print("Fatal: AI_OPS_AUTH_TOKEN is not set.")
            sys.exit(1)
