from starlette.exceptions import HTTPException


def get_bearer_token(request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")
    return token


def require_admin(request):
    token = get_bearer_token(request)
    if token != request.app.state.api_config.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return token


def require_user(request):
    token = get_bearer_token(request)
    user = request.app.state.service.get_user_from_token(token)
    if user is None:
        raise HTTPException(status_code=403, detail="Invalid user token")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")
    return user
