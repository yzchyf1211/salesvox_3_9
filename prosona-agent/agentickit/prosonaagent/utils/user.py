from agentickit.core.context.agentic_context_manager import context_saver

def get_token(context_id: str):
    agentic_context = context_saver.load(context_id)
    request_header = agentic_context.get("request_header", {})
    token = request_header.get("token", "")
    return token

def get_user_profile(context_id: str):
    agentic_context = context_saver.load(context_id)
    user_profile = agentic_context.get("user_profile", {})
    return user_profile