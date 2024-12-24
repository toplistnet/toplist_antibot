from muffin import Request, Application, Response, ResponseError, ResponseHTML
from app.app import app
from urllib import parse as parse
from app.tools.utils import Config

def SetIP(request: Request) -> None:
    ip: str = request.headers.get("CF-Connecting-IP", default='')
    if not ip:
        ip = request.headers.get("X-Forwarded-For", default='')
    if not ip:
        ip = "127.0.0.1"

    request.scope.setdefault("ip", ip)
    
def SetLanguage(request: Request) -> None:
    langs: list[str] = str(object=Config(key="locales", default="en")).split(sep=",")
    lang: str = request.headers.get("CF-IPCountry", default="")
    request.scope.setdefault("ip_country", lang)
    if not lang or lang not in langs:
        lang = request.headers.get("accept-language", default="en")[:2]
    lang = request.cookies.get('lang', lang)
    if not lang or lang not in langs:
        lang = 'en'

    request.scope.setdefault("lang", lang)
    request.scope.setdefault("ip_country", request.headers.get("CF-IPCountry", default="").upper())

async def parse_post_data(r: Request) -> dict:
    query: str = await r.text()
    post: dict = dict(parse.parse_qsl(qs=query))
    for k, v in post.items():
        if v.isdigit():
            post[k] = int(v)
    return post
    
async def SetPostDict(r: Request) -> bool:    
    if 'POST' in str(object=r.items()):
        r.scope.setdefault('post', await parse_post_data(r=r))
        return True
    
    return False

@app.middleware
async def my_middleware(app_func: Application, request: Request, receive, send) -> None:
    SetIP(request=request)
    SetLanguage(request=request)
    await SetPostDict(r=request)
    
    response: Response|None = await app_func(request, receive, send)
    if type(response) == Response:
        response.headers['server'] = "captcha_server" # TODO: validate on live settings

    return response

@app.on_error(etype=ResponseError)
async def process_http_errors(r: Request, response_error) -> Response:
    if response_error.status_code == 404:
        return ResponseHTML(status_code=response_error.status_code, content="")
    return ResponseHTML(content=f"Error: {response_error}")
