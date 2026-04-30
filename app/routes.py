import random
import aiohttp
from app.app import app, redis, db, jinja2, localization
from muffin import Request, Response, ResponseError, ResponseHTML, ResponseJSON, ResponseRedirect
import app.tools.utils as utils
import json
import app.captcha1 as captcha1
import app.captcha2 as captcha2
import app.captcha3 as captcha3
import time

captchas: dict = {
    1 : {
        'count' : -1,
        'min_count' : int(utils.Config(key="captcha1_pregeneration_count", default="10")),
        'generate' : captcha1.Generate,
        'validate' : captcha1.Validate,
        'check_click' : captcha1.CheckClick,
        'template' : "1/index.html",
        'width' : 407,
        'height' : 268,
        'set_name' : f"captcha1_v{captcha1.VERSION}",
    },
    2 : {
        'count' : -1,
        'min_count' : int(utils.Config(key="captcha2_pregeneration_count", default="10")),
        'generate' : captcha2.Generate,
        'validate' : captcha2.Validate,
        'template' : "2/index.html",
        'width' : 402,
        'height' : 400,
        'set_name' : f"captcha2_v{captcha2.VERSION}",
    },
    3 : {
        'count' : -1,
        'min_count' : int(utils.Config(key="captcha3_pregeneration_count", default="10")),
        'generate' : captcha3.Generate,
        'validate' : captcha3.Validate,
        'check_click' : captcha3.CheckClick,
        'template' : "3/index.html",
        'width' : 407,
        'height' : 268,
        'set_name' : f"captcha3_v{captcha3.VERSION}",
    },
    'stats' : {
        "captcha_button_rendered": 0,
        "captcha1_rendered": 0,
        "captcha2_rendered": 0,
        "captcha3_rendered": 0,
        "captcha1_generated": 0,
        "captcha2_generated": 0,
        "captcha3_generated": 0,
        "captcha1_validations": 0,
        "captcha2_validations": 0,
        "captcha3_validations": 0,
        "captcha1_validations_succeeded": 0,
        "captcha2_validations_succeeded": 0,
        "captcha3_validations_succeeded": 0,
        "captcha1_validations_failed": 0,
        "captcha2_validations_failed": 0,
        "captcha3_validations_failed": 0,
        "captcha1_validations_ratio": 0,
        "captcha2_validations_ratio": 0,
        "captcha3_validations_ratio": 0,
    },
}

async def LoadStats() -> None:
    for name in captchas['stats'].keys():
        captchas['stats'][name] = int(await redis.zscore(name="STATS:GENERAL", value=name) or 0)

async def SyncCaptchaUsers() -> None:
    rows: list[dict] = await db.query(query="SELECT id, sitekey, secretkey, hosts FROM captcha_users")
    if not rows:
        return

    for row in rows:
        await redis.sadd("USERS", row['id'])
        await redis.sadd("SITEKEYS", row['sitekey'])
        await redis.sadd("SECRETKEYS", row['secretkey'])
        hosts: list = [h for h in (row.get('hosts') or '').split(',') if h]
        if hosts:
            await redis.sadd(f"HOSTS:{row['sitekey']}", *hosts)
    
async def EnsureCaptchaAvailability() -> None:
    global captchas
    for captcha_type, captcha_data in captchas.items():
        if not str(object=captcha_type).isdigit():
            continue

        while True:
            captchas[captcha_type]['count'] = await redis.scard(name=captcha_data['set_name']) or 0
            if captcha_data['count'] >= captcha_data['min_count']:
                break

            data: dict = captcha_data['generate']()
            if not data['status']:
                continue

            await redis.sadd(captcha_data['set_name'], json.dumps(obj=data))
            captchas['stats'][f"captcha{captcha_type}_generated"] = \
                int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_generated"))

async def AfterRequest() -> None:
    await EnsureCaptchaAvailability()
    await localization.Save()

@app.route('/', methods=['GET'])
async def route_index(r: Request) -> Response:
    if int(utils.Config(key="debug", default="0")):
        return ResponseRedirect(url="/test")
    return ResponseRedirect(url="https://metin2pserver.net/Captcha-System-More-Reliable-Anti-Bot-System")

@app.route('/stats', methods=['GET'])
async def route_stats(r: Request) -> Response:
    for captcha_type in captchas.keys():
        if not str(object=captcha_type).isdigit():
            continue
        
        validations_failed: int = captchas['stats'][f'captcha{captcha_type}_validations_failed']
        validations: int = captchas['stats'][f'captcha{captcha_type}_validations']
        captchas['stats'][f'captcha{captcha_type}_validations_ratio'] = \
            f"{max(1, validations_failed)/max(1, validations)*100:.2f}%"

    return ResponseHTML(content=utils.safe_serialize(obj=captchas))

@app.route('/captcha/button/{sitekey:str}', methods=['GET'])
async def route_captcha_button(r: Request) -> Response:
    ref: str = r.headers.get("Referer", default="")
    if not ref or '://' not in ref:
        return ResponseError(status_code=403, message="No Direct Access Allowed")
    
    ref = ref.split('://', 1)[1]
    if '/' not in ref:
        return ResponseError(status_code=403, message="No Direct Access Allowed")
    
    ref = ref.split("/", 1)[0]
    sitekey: str = r.path_params.get("sitekey", "")
    if not await redis.sismember(name=f"HOSTS:{sitekey}", value=ref):
        print(f"Host-Domain Not Allowed: {ref} - {sitekey}")
    #     return ResponseError(status_code=403, message="Host-Domain Not Allowed")
    
    if not await redis.sismember(name="SITEKEYS", value=sitekey):
        return ResponseError(status_code=403, message="Site-Key Not Allowed")
    
    captcha_type = -1
    forced: str = r.query.get('captcha_type', default='')
    if forced.isdigit() and int(forced) in captchas:
        captcha_type: int = int(forced)
        
    context: dict = {
        "locale" : r.lang,
        "sitekey" : sitekey,
        "sitekey_hash" : utils.FastHash(input=f"{sitekey}_allowgeneration_{app.cfg.name}"),
        "captcha_type" : captcha_type,
    }

    captchas['stats'][f"captcha_button_rendered"] = \
        int(await redis.zincrby(name="STATS:GENERAL", amount=1, value="captcha_button_rendered"))

    captcha_template: str = "captcha_button_checkbox.html"
    if ref != 'metin2pserver.net':
        captcha_template = "captcha_button_checkbox_external.html"

    return ResponseHTML(content=await jinja2.render(path=captcha_template, **context))

@app.route("/captcha/display/{sitekey:str}/{sitekey_hash:str}", methods=['GET'])
async def route_gen_captcha(r: Request) -> Response:
    chash: str = utils.FastHash(input=f"{r.path_params.get('sitekey', '')}_allowgeneration_{app.cfg.name}")
    if r.path_params.get("sitekey_hash", "") != chash:
        return ResponseError(status_code=403, message="Invalid Site Key Hash")

    app.run_after_response(AfterRequest())
    await EnsureCaptchaAvailability()

    _id: int = await redis.incr(name="captcha_serial_id")

    forced: str = r.query.get('captcha_type', default='')
    if forced.isdigit() and int(forced) in captchas:
        captcha_type: int = int(forced)
    else:
        types_cfg: str = str(object=utils.Config(key='captcha_default_types', default='1,2'))
        pool: list[int] = [int(t) for t in types_cfg.split(',') if t.strip().isdigit() and int(t) in captchas]
        if not pool:
            pool = [k for k in captchas.keys() if isinstance(k, int)]
        captcha_type = random.choice(seq=pool)

    _data: bytes | float | int | str = await redis.spop(name=captchas[captcha_type]['set_name']) or ''
    data: dict = json.loads(s=str(object=_data))

    sitekey: str = r.path_params.get("sitekey", "")
    timestamp: int = int(time.time())
    context: dict = {
        'captcha_id' : _id,
        'hash' : utils.FastHash(input=f"{_id}_{captcha_type}_{timestamp}_{sitekey}"),
        'img' : data['bg_base64'],
        'translate' : localization.Translate,
        'Config' : utils.Config,
        'locale' : r.lang,
        'element_name' : r.query.get('element_name', default='aa'),
        'timestamp' : timestamp,
        'sitekey' : sitekey,
        'width' : captchas[captcha_type]['width'],
        'height' : captchas[captcha_type]['height'],
    }
    
    if int(utils.Config(key="debug", default="0")):
        print('Captcha_Type: ' + str(captcha_type))
        
    if captcha_type == 1 or captcha_type == 3:
        await redis.set(name=f"captcha_{_id}", value=json.dumps(obj=data['icon_coordinates']), ex=60*10)
        context.update({
            'icons' : data['icons_base64'],
            'icons_count' : data['icons_count'],
        })
    elif captcha_type == 2:
        await redis.set(name=f"captcha_{_id}", value=json.dumps(obj=data['data']), ex=60*10)
    else:
        return ResponseError(status_code=403, message="Unknown captcha_type")
    
    html: str = await jinja2.render(path=captchas[data['type']]['template'], **context)
    await redis.zincrby(name="IPSTATS:CAPTCHA:GENERATED", amount=1, value=r.ip)

    captchas['stats'][f"captcha{captcha_type}_rendered"] = \
        int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_rendered"))
    return ResponseHTML(content=html)
    
CHECK_CLICK_FAIL_LIMIT: int = int(utils.Config(key='captcha_check_click_fail_limit', default="30"))

@app.route("/captcha/check_click", methods=['POST'])
async def web_check_captcha_click(r: Request) -> Response:
    response: dict = {'ok': False}
    post: dict[str, str] = r.post

    try:
        if not post.keys() >= {'captcha_id', 'captcha_type', 'hash', 'timestamp', 'sitekey', 'index', 'x', 'y'}:
            return ResponseJSON(content=response)

        captcha_type: int = int(post['captcha_type'])
        if captcha_type not in captchas or 'check_click' not in captchas[captcha_type]:
            return ResponseJSON(content=response)

        c_hash: str = utils.FastHash(input=f"{post['captcha_id']}_{captcha_type}_{post['timestamp']}_{post['sitekey']}")
        if c_hash != post['hash']:
            return ResponseJSON(content=response)

        db_data_str: str | bytes | None = await redis.get(name=f"captcha_{post['captcha_id']}")
        if not db_data_str:
            response['expired'] = True
            return ResponseJSON(content=response)

        db_data: list = json.loads(s=db_data_str)
        index: int = int(post['index'])
        x: int = int(float(post['x']))
        y: int = int(float(post['y']))

        if captchas[captcha_type]['check_click'](db_data=db_data, index=index, x=x, y=y):
            response['ok'] = True
            now_ms: int = int(time.time() * 1000)
            await redis.rpush(f"captcha_click_times_{post['captcha_id']}", now_ms)
            await redis.expire(name=f"captcha_click_times_{post['captcha_id']}", time=60*10)
            utils.dprint(f"[check_click] HIT  type={captcha_type} id={post['captcha_id']} idx={index} click=({x},{y}) t_ms={now_ms}")
        else:
            fails: int = int(await redis.incr(name=f"captcha_check_fails_{post['captcha_id']}"))
            await redis.expire(name=f"captcha_check_fails_{post['captcha_id']}", time=60*10)
            utils.dprint(f"[check_click] MISS type={captcha_type} id={post['captcha_id']} idx={index} click=({x},{y}) fails={fails}/{CHECK_CLICK_FAIL_LIMIT}")
            if fails >= CHECK_CLICK_FAIL_LIMIT:
                await redis.delete(f"captcha_{post['captcha_id']}")
                response['expired'] = True

    except Exception as e:
        utils.dprint(f"[check_click] {type(e).__name__}: {e}\n{utils.stacktrace()}")

    return ResponseJSON(content=response)

@app.route("/captcha/validate", methods=['POST'])
async def web_validate_captcha(r: Request) -> Response:
    validation: dict = { 'status' : False }
    post: dict[str, str] = r.post

    try:
        captcha_type: int = -1

        if not post.keys() >= {'captcha_id', 'captcha_type', 'hash', 'timestamp', 'sitekey'}:
            raise ValueError("missing parameters")
        
        captcha_type = int(post['captcha_type'])

        c_hash: str = utils.FastHash(input=f"{post['captcha_id']}_{captcha_type}_{post['timestamp']}_{post['sitekey']}")
        if c_hash != post['hash']:
            raise ValueError("hash mismatch")
    
        db_data_str: bytes = await redis.getdel(name=f"captcha_{post['captcha_id']}") or b'{}'

        if not captcha_type in captchas:
            raise ValueError("unknown captcha_type")
        elif not db_data_str:
            raise ValueError("captcha data not found")
        
        captchas['stats'][f"captcha{captcha_type}_validations"] = \
            int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_validations"))
        
        db_data: dict = json.loads(s=db_data_str)
        captchas[captcha_type]['validate'](db_data=db_data, post_data=post)

    except ValueError as e:
        validation['error'] = str(object=e)
        utils.dprint(f"[validate] ValueError: {e} | type={captcha_type} sitekey={post.get('sitekey','?')} "
                     f"captcha_id={post.get('captcha_id','?')} ip={r.ip} hash={post.get('hash','?')} "
                     f"ts={post.get('timestamp','?')}")

    except Exception as e:
        validation['error'] = str(object=e)
        utils.dprint(f"[validate] {type(e).__name__}: {e} | type={captcha_type} sitekey={post.get('sitekey','?')} "
                     f"captcha_id={post.get('captcha_id','?')} ip={r.ip}\n{utils.stacktrace()}")

    finally:
        if 'error' in validation:
            if 'sitekey' in post:
                await redis.zincrby(name="STATS:CAPTCHA:FAILED", amount=1, value=post['sitekey'])
            await redis.zincrby(name="IPSTATS:CAPTCHA:FAILED", amount=1, value=r.ip)
            captchas['stats'][f"captcha{captcha_type}_validations_failed"] = \
                int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_failed"))
            return ResponseJSON(content=validation)

        result_token: str = utils.FastHash(input=f"{post['sitekey']}__{app.cfg.name}_{post['captcha_id']}")
        try:
            duration: float = round(time.time() - float(post.get('timestamp', 0)), 3)
            if duration < 0 or duration > 86400:
                duration = 0
        except (TypeError, ValueError):
            duration = 0

        click_times_key: str = f"captcha_click_times_{post['captcha_id']}"
        raw_times: list = await redis.lrange(click_times_key, 0, -1) or []
        click_times_ms: list = [int(t) for t in raw_times]
        click_intervals_ms: list = [0] + [click_times_ms[i] - click_times_ms[i-1] for i in range(1, len(click_times_ms))]
        click_intervals: str = ",".join(str(d) for d in click_intervals_ms)
        await redis.delete(click_times_key)
        await redis.delete(f"captcha_check_fails_{post['captcha_id']}")

        await redis.set(name=f"captcha_result_{result_token}", value=json.dumps(obj={
            "remoteip" : r.ip,
            "captcha_type" : captcha_type,
            "duration" : duration,
            "click_intervals" : click_intervals,
        }), ex=60*10)

        await redis.zincrby(name="STATS:CAPTCHA:SUCCESS", amount=1, value=post['sitekey'])
        await redis.hincrby(name="IPSTATS:CAPTCHA:SUCCESS", amount=1, key=r.ip)
        captchas['stats'][f"captcha{captcha_type}_validations_succeeded"] = \
            int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_succeeded"))
        
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
                    'secret': "your_secretkey",
                    'response': r.post.get('g-recaptcha-response', ''),
                    'remoteip': r.ip,
                }
    
    async with aiohttp.ClientSession() as sess:
        url: str = f"{utils.Config(key='url')}captcha/api/siteverify"
        async with sess.post(url=url, data=payload) as resp:
            data: dict = await resp.json() or {}
            return ResponseJSON(content={'POST_DATA' : r.post, 'captcha_verify' : data})


app.on_startup(fn=utils.PrepareDataset)
app.on_startup(fn=EnsureCaptchaAvailability)
app.on_startup(fn=LoadStats)
app.on_startup(fn=SyncCaptchaUsers)
