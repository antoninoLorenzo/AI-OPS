from dotenv import load_dotenv

from ai_ops.api.auth import setup_auth
from ai_ops.api.config import get_settings

from ai_ops.core.conversation import ConversationStoreStrategy

# some things in core rely on environment variables
load_dotenv()

# the following setup needs to run before the app construction, that's because `setup_auth` 
# binds the proper strategy to the `handle_api_key` app dependency.
_ = get_settings()
setup_auth()
