import random
import aiohttp
from app.app import app, redis, jinja2, localization, db
from muffin import Request, Response, ResponseError, ResponseHTML, ResponseJSON, Application
import app.tools.utils as utils
import json
from urllib import parse
import app.captcha1 as captcha1
import app.captcha2 as captcha2
import time

captchas: dict = {
    1 : {
        'count' : -1,
        'min_count' : int(utils.Config(key="captcha1_pregeneration_count", default="10")),
        'generate' : captcha1.Generate,
        'validate' : captcha1.Validate,
        'template' : "1/index.html",
        'width' : 400,
        'height' : 400,
    },
    2 : {
        'count' : -1,
        'min_count' : int(utils.Config(key="captcha2_pregeneration_count", default="10")),
        'generate' : captcha2.Generate,
        'validate' : captcha2.Validate,
        'template' : "2/index.html",
        'width' : 500,
        'height' : 500,
    },
}

async def EnsureCaptchaAvailability() -> None:
    global captchas
    for captcha_type, captcha_data in captchas.items():
        while True:
            captchas[captcha_type]['count'] = await redis.scard(name=f"captcha{captcha_type}") or 0
            if captcha_data['count'] >= captcha_data['min_count']:
                break

            data: dict = captcha_data['generate']()
            if not data['status']:
                continue

            await redis.sadd(f"captcha{captcha_type}", json.dumps(obj=data))

async def AfterRequest() -> None:
    await EnsureCaptchaAvailability()
    await localization.Save()

@app.route('/')
async def route_home(r: Request) -> Response:
    return ResponseHTML(content=str(object=captchas))

@app.route('/captcha/button/{sitekey:str}', methods=['GET'])
async def route_captcha_button(r: Request) -> Response:
    # TODO: whitelist referrer domains only
    ref: str = r.headers.get("Referer", default="")
    if not ref or '://' not in ref:
        return ResponseError(status_code=403, message="No Direct Access Allowed")
    
    ref = ref.split('://', 1)[1]
    if '/' not in ref:
        return ResponseError(status_code=403, message="No Direct Access Allowed")
    
    ref = ref.split("/", 1)[0]
    sitekey: str = r.path_params.get("sitekey", "")
    # ref_whitelist: tuple = ('t.metin2pserver.net:8099', )
    # if ref not in ref_whitelist:
    if not await redis.sismember(name=f"HOSTS:{sitekey}", value=ref):
        return ResponseError(status_code=403, message="Host-Domain Not Allowed")
    
    if not await redis.sismember(name="SITEKEYS", value=sitekey):
        return ResponseError(status_code=403, message="Site-Key Not Allowed")
    
    context: dict = {
        "locale" : "en",
        # TODO translate button texts..
        "sitekey" : sitekey,
        "sitekey_hash" : utils.FastHash(input=f"{sitekey}_allowgeneration_{app.cfg.name}"),
    }
    html: str = await jinja2.render(path="captcha_button.html", **context)
    return ResponseHTML(content=html)

@app.route("/captcha/display/{sitekey:str}/{sitekey_hash:str}", methods=['GET'])
async def route_gen_captcha(r: Request) -> Response:
    chash: str = utils.FastHash(input=f"{r.path_params.get('sitekey', '')}_allowgeneration_{app.cfg.name}")
    if r.path_params.get("sitekey_hash", "") != chash:
        return ResponseError(status_code=403, message="Invalid Site Key Hash")

    app.run_after_response(AfterRequest())
    await EnsureCaptchaAvailability()

    _id: int = await redis.incr(name="captcha_serial_id")
    captcha_type: int = random.randint(a=1, b=2) # TODO: add logic
    _data: bytes | float | int | str = await redis.spop(name=f"captcha{captcha_type}") or ''
    data: dict = json.loads(s=str(object=_data))

    sitekey: str = r.path_params.get("sitekey", "")
    timestamp: int = int(time.time())
    context: dict = {
        'captcha_id' : _id,
        'hash' : utils.FastHash(input=f"{_id}_{captcha_type}_{timestamp}_{sitekey}"),
        'img' : data['bg_base64'],
        'translate' : localization.Translate,
        'Config' : utils.Config,
        'locale' : 'en',
        'element_name' : r.query.get('element_name', default='aa'),
        'timestamp' : timestamp,
        'sitekey' : sitekey,
        'width' : captchas[captcha_type]['width'],
        'height' : captchas[captcha_type]['height'],
    }
    
    if captcha_type == 1:
        await redis.set(name=f"captcha_{_id}", value=json.dumps(obj=data['icon_coordinates']), ex=60*10)
        context.update({
            'icons' : data['icons_base64'],
            'icons_count' : data['icons_count'], 
        })
    elif captcha_type == 2:
        await redis.set(name=f"captcha_{_id}", value=json.dumps(obj=data['data']), ex=60*10)
        print(f"c2 SHOULD BE {data['data']}")
    else:
        return ResponseError(status_code=403, message="Unknown captcha_type")
    
    html: str = await jinja2.render(path=captchas[data['type']]['template'], **context)
    return ResponseHTML(content=html)
    
@app.route("/captcha/validate", methods=['POST'])
async def web_validate_captcha(r: Request) -> Response:
    validation: dict = { 'status' : False }
    post: dict[str, str] = r.post

    try:
        if not post.keys() >= {'captcha_id', 'captcha_type', 'hash', 'timestamp', 'sitekey'}:
            raise ValueError("missing parameters")
        
        c_hash: str = utils.FastHash(input=f"{post['captcha_id']}_{post['captcha_type']}_{post['timestamp']}_{post['sitekey']}")
        if c_hash != post['hash']:
            raise ValueError("hash mismatch")
    
        db_data_str: bytes = await redis.getdel(name=f"captcha_{post['captcha_id']}") or b'{}'

        if not post['captcha_type'] in captchas:
            raise ValueError("unknown captcha_type")
        elif not db_data_str:
            raise ValueError("captcha data not found")
        
        db_data: dict = json.loads(s=db_data_str)
        captchas[post['captcha_type']]['validate'](db_data=db_data, post_data=post)

    except ValueError as e:
        validation['error'] = str(object=e)

    except Exception as e:
        validation['error'] = str(object=e)

    finally:
        if 'error' in validation:
            await redis.zincrby(name="STATS:CAPTCHA:FAILED", amount=1, value=r.post['sitekey'])
            return ResponseJSON(content=validation)

        result_token: str = utils.FastHash(input=f"{r.post['sitekey']}__{app.cfg.name}_{post['captcha_id']}")
        await redis.set(name=f"captcha_result_{result_token}", value=r.ip, ex=60*10)
        await redis.zincrby(name="STATS:CAPTCHA:SUCCESS", amount=1, value=r.post['sitekey'])

        return ResponseJSON(content={
            'status' : True,
            'result' : result_token,
        })

@app.route("/test", methods=['POST', 'GET'])
async def route_display_captcha_test(r: Request) -> Response:
    if r.method == 'GET':
        return ResponseHTML(content=await jinja2.render(path="test.html", **{}))
    
    if not r.post.keys() >= {'g-recaptcha-response', 'secret'}:
        payload: dict[str, str] = {
                    'secret': r.post['secret'],
                    'response': r.post.get('g-recaptcha-response', ''),
                    'remoteip': r.ip,
                }
    
    async with aiohttp.ClientSession() as sess:
        url: str = f"{utils.Config(key='url')}captcha/api/siteverify"
        async with sess.post(url=url, data=payload) as resp:
            data: dict = await resp.json() or {}
            return ResponseJSON(content={'POST_DATA' : r.post, 'captcha_verify' : data})

    return ResponseJSON(content=r.post)

@app.route("/captcha/api/siteverify", methods=['POST'])
async def route_captcha_api_siteverify(r: Request) -> Response:
    response: dict = {
        "success" : False, 
        "error-codes" : [],
        "risk_score" : 0,
        "risk_information" : ["not-implemented"]
    }

    try:
        if not r.post.keys() >= {'secret', 'response'}:
            raise ValueError("missing-input-response")

        if not await redis.sismember(name="SECRETKEYS", value=r.post['secret']):
            raise ValueError("invalid-input-secret")
        
        ip: bytes = await redis.getdel(name=f"captcha_result_{r.post['response']}") or b''
        if not ip:
            await redis.zincrby(name="STATS:VALIDATION:FAILED", amount=1, value=r.post['secret'])
            raise ValueError("invalid-input-response")
        
        if 'ip' in r.post:
            response['ip'] = r.post['ip'] == ip.decode()

        await redis.zincrby(name="STATS:VALIDATION:SUCCESS", amount=1, value=r.post['secret'])
        response["success"] = True
        # TODO: risk score calculation
        # TODO: add proxycheck information?

    except ValueError as e:
        response['error-codes'].append(str(object=e))

    finally:
        if 'ip' in r.post and 'ip' not in response:
            response['ip'] = True

        if 'extra' in r.post:
            response['captcha_type'] = 0
            response['captchas'] = 0
            response['valid'] = 0
            response['invalid'] = 0

        return ResponseJSON(content=response)

@app.route("/api/account/add", methods=['POST'])
async def route_api_account_add(r: Request) -> Response:
    if not r.headers.get("Authorization") == f"Bearer {utils.Config(key='api_key', default='_ADMIN78_12_21')}":
        return ResponseJSON(content={"status" : False, "error" : "unauthorized"})
    
    if not r.post.keys() >= {'hosts', 'email'}:
        return ResponseJSON(content={"status" : False, "error" : "missing parameters"})
    
    if await db.queryField(query="SELECT id FROM captcha_users WHERE email=:email", args={'email' : r.post['email']}):
        return ResponseJSON(content={"status" : False, "error" : "user already exists"})
    
    hosts: set = utils.ValidateHosts(input=r.post['hosts'])
    if not hosts:
        return ResponseJSON(content={"status" : False, "error" : "invalid host, must be a valid domain or ip:port"})

    if len(hosts) > 10:
        return ResponseJSON(content={"status" : False, "error" : "too many hosts, max 10 allowed"})

    sitekey: str = utils.FastHash(input=f"{r.post['email']}_{app.cfg.name}_{time.time()}")
    secretkey: str = utils.FastHash(input=f"SECRET_KEY_{sitekey}_{app.cfg.name}")

    captcha_user_id: int = await db.insert(table='captcha_users', data={
        'email' : r.post['email'], 
        'sitekey' : sitekey, 
        'secretkey' : secretkey,
        'hosts' : ','.join(hosts),
    })
    await redis.sadd("USERS", captcha_user_id)
    await redis.sadd("SITEKEYS", sitekey)
    await redis.sadd("SECRETKEYS", secretkey)
    await redis.sadd(f"HOSTS:{sitekey}", *hosts)

    return ResponseJSON(content={
        "status" : True, 
        'captcha_user_id' : captcha_user_id,
        'sitekey' : sitekey,
        'secretkey' : secretkey,
    })

@app.route("/api/account/remove", methods=['POST'])
async def route_api_account_remove(r: Request) -> Response:
    if not r.headers.get("Authorization") == f"Bearer {utils.Config(key='api_key', default='_ADMIN78_12_21')}":
        return ResponseJSON(content={"status" : False, "error" : "unauthorized"})
    
    if not r.post.keys() >= {'captcha_user_id'}:
        return ResponseJSON(content={"status" : False, "error" : "missing parameters"})
    
    user: dict = await db.queryRowDict(query="SELECT * FROM captcha_users WHERE id=:id", args={
        'id' : r.post['captcha_user_id']
    })
    
    await redis.srem("USERS", user['id'])
    await redis.srem("SITEKEYS", user['sitekey'])
    await redis.srem("SECRETKEYS", user['secretkey'])
    await redis.delete(f"HOSTS:{user['sitekey']}")
    await db.query(query="DELETE FROM captcha_users WHERE id=:id", args={
        'id' : user['id']
    })
    
    return ResponseJSON(content={"status" : True})

@app.route("/api/account/regenerate", methods=['POST'])
async def route_api_account_regenerate(r: Request) -> Response:
    if not r.headers.get("Authorization") == f"Bearer {utils.Config(key='api_key', default='_ADMIN78_12_21')}":
        return ResponseJSON(content={"status" : False, "error" : "unauthorized"})
    
    if not r.post.keys() >= {'captcha_user_id'}:
        return ResponseJSON(content={"status" : False, "error" : "missing parameters"})
    
    user: dict = await db.queryRowDict(query="SELECT * FROM captcha_users WHERE id=:id", args={
        'id' : r.post['captcha_user_id']
    })
    if not user:
        return ResponseJSON(content={"status" : False, "error" : "user not found"})
    
    # TODO: copy ranking to new sitekey
    await redis.srem("SITEKEYS", user['sitekey'])
    await redis.srem("SECRETKEYS", user['secretkey'])
    await redis.zrem("STATS:CAPTCHA:SUCCESS", user['sitekey'])
    await redis.zrem("STATS:CAPTCHA:FAILED", user['sitekey'])
    await redis.delete(f"HOSTS:{user['sitekey']}")

    sitekey: str = utils.FastHash(input=f"{user['email']}_{app.cfg.name}_{time.time()}")
    secretkey: str = utils.FastHash(input=f"SECRET_KEY_{sitekey}_{app.cfg.name}")
    await redis.set(f"HOSTS:{sitekey}", *user['hosts'].split(','))
            
    return ResponseJSON(content={"status" : True})

@app.route("/api/account/hosts", methods=['POST'])
async def route_api_account_hosts(r: Request) -> Response:
    if not r.headers.get("Authorization") == f"Bearer {utils.Config(key='api_key', default='_ADMIN78_12_21')}":
        return ResponseJSON(content={"status" : False, "error" : "unauthorized"})
    
    if not r.post.keys() >= {'captcha_user_id', 'hosts'}:
        return ResponseJSON(content={"status" : False, "error" : "missing parameters"})

    sitekey = await db.queryField(query="SELECT sitekey FROM captcha_users WHERE id=:id", args={
        'id' : r.post['captcha_user_id']
    })

    if not sitekey:
        return ResponseJSON(content={"status" : False, "error" : "User Not Found"})
    
    hosts: set = utils.ValidateHosts(input=r.post['hosts'])
    if not hosts:
        return ResponseJSON(content={"status" : False, "error" : "invalid host, must be a valid domain or ip:port"})

    if len(hosts) > 10:
        return ResponseJSON(content={"status" : False, "error" : "too many hosts, max 10 allowed"})
    
    await redis.delete(f"HOSTS:{sitekey}")
    await redis.sadd(name=f"HOSTS:{sitekey}", *hosts)
    await db.update(query="UPDATE captcha_users SET hosts=:hosts WHERE id=:id", args={
        "id" : r.post['captcha_user_id'],
        "hosts" : ",".join(hosts),
    })

    return ResponseJSON(content={"status" : True})

@app.route("/api/account/stats", methods=['POST'])
async def route_api_account_stats(r: Request) -> Response:
    if not r.headers.get("Authorization") == f"Bearer {utils.Config(key='api_key', default='_ADMIN78_12_21')}":
        return ResponseJSON(content={"status" : False, "error" : "unauthorized"})
    
    if not r.post.keys() >= {'captcha_user_id'}:
        return ResponseJSON(content={"status" : False, "error" : "missing parameters"})
    
    data = await db.queryRow(query="SELECT sitekey, secretkey FROM captcha_users WHERE id=:id", args={
        'id' : r.post['captcha_user_id']
    })

    if not data:
        return ResponseJSON(content={"status" : False, "error" : "User Not Found"})
    
    stats: dict = {
        'captchas' : {
            'success' : await redis.zscore(name="STATS:CAPTCHA:SUCCESS", value=data['sitekey']) or 0,
            'failed' : await redis.zscore(name="STATS:CAPTCHA:FAILED", value=data['sitekey']) or 0,
        },
        'validations' : {
            'success' : await redis.zscore(name="STATS:VALIDATION:SUCCESS", value=data['secretkey']) or 0,
            'failed' : await redis.zscore(name="STATS:VALIDATION:FAILED", value=data['secretkey']) or 0,
        },
        'hosts' : await redis.smembers(name=f"HOSTS:{r.post['captcha_user_id']}"),
    }

    return ResponseJSON(content=stats)

@app.middleware
async def my_middleware(app_func: Application, request: Request, receive, send) -> None:
    ip: str = request.headers.get("CF-Connecting-IP", default=request.headers.get("X-Forwarded-For", default='127.0.0.1'))
    request.scope.setdefault("ip", ip)
    if 'POST' in str(object=request.items()):
        query: str = await request.text()
        post_data: dict = dict(parse.parse_qsl(qs=query))
        
        for k,v in post_data.items():
            if v.isdigit():
                post_data[k] = int(v)

        request.scope.setdefault('post', post_data)
    
    response: Response|None = await app_func(request, receive, send)
    response.headers['server'] = "captcha_server" # TODO: validate on live settings
    return response

app.on_startup(fn=utils.PrepareDataset)
app.on_startup(fn=EnsureCaptchaAvailability)
app.on_startup(fn=localization.Load)
