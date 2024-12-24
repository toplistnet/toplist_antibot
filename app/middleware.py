from muffin import Request, Application, Response, ResponseError, ResponseHTML
from app.app import app
from urllib import parse as parse

@app.middleware
async def my_middleware(app_func: Application, request: Request, receive, send) -> None:
    ip: str = request.headers.get("CF-Connecting-IP", default=request.headers.get("X-Forwarded-For", default='127.0.0.1'))
    request.scope.setdefault("ip", ip)

    if 'POST' in str(object=request.items()):
        query: str = await request.text()
        post: dict = dict(parse.parse_qsl(qs=query))
        
        for k,v in post.items():
            if v.isdigit():
                post[k] = int(v)

        request.scope.setdefault('post', post)
    
    response: Response|None = await app_func(request, receive, send)
    if type(response) == Response:
        response.headers['server'] = "captcha_server" # TODO: validate on live settings

    return response

@app.on_error(etype=ResponseError)
async def process_http_errors(r: Request, response_error) -> Response:
    if response_error.status_code == 404:
        return ResponseHTML(status_code=response_error.status_code, content="")
    return ResponseHTML(content=f"Error: {response_error}")
