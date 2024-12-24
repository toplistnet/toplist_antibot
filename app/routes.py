import random
import aiohttp
from app.app import app, redis, jinja2, localization
from muffin import Request, Response, ResponseError, ResponseHTML, ResponseJSON, ResponseRedirect
import app.tools.utils as utils
import json
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
    'stats' : {
        "captcha_button_rendered": 0,
        "captcha1_rendered": 0,
        "captcha2_rendered": 0,
        "captcha1_generated": 0,
        "captcha2_generated": 0,
        "captcha1_validations": 0,
        "captcha2_validations": 0,
        "captcha1_validations_succeeded": 0,
        "captcha2_validations_succeeded": 0,
        "captcha1_validations_failed": 0,
        "captcha2_validations_failed": 0,
        "captcha1_validations_ratio": 0,
        "captcha2_validations_ratio": 0,
    },
}

async def LoadStats() -> None:
    for name in captchas['stats'].keys():
        captchas['stats'][name] = int(await redis.zscore(name="STATS:GENERAL", value=name) or 0)
    
async def EnsureCaptchaAvailability() -> None:
    global captchas
    for captcha_type, captcha_data in captchas.items():
        if not str(object=captcha_type).isdigit():
            continue

        while True:
            captchas[captcha_type]['count'] = await redis.scard(name=f"captcha{captcha_type}") or 0
            if captcha_data['count'] >= captcha_data['min_count']:
                break

            data: dict = captcha_data['generate']()
            if not data['status']:
                continue
            
            await redis.sadd(f"captcha{captcha_type}", json.dumps(obj=data))
            captchas['stats'][f"captcha{captcha_type}_generated"] = \
                int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_generated"))

async def AfterRequest() -> None:
    await EnsureCaptchaAvailability()
    await localization.Save()

@app.route('/', methods=['GET'])
async def route_index(r: Request) -> Response:
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
        utils.dprint(f"Host-Domain Not Allowed: {ref} - {sitekey}")
        return ResponseError(status_code=403, message="Host-Domain Not Allowed")
    
    if not await redis.sismember(name="SITEKEYS", value=sitekey):
        return ResponseError(status_code=403, message="Site-Key Not Allowed")
    
    context: dict = {
        "locale" : r.lang,
        "sitekey" : sitekey,
        "sitekey_hash" : utils.FastHash(input=f"{sitekey}_allowgeneration_{app.cfg.name}"),
    }

    captchas['stats'][f"captcha_button_rendered"] = \
        int(await redis.zincrby(name="STATS:GENERAL", amount=1, value="captcha_button_rendered"))

    return ResponseHTML(content=await jinja2.render(path="captcha_button.html", **context))

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
        'locale' : r.lang,
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
    else:
        return ResponseError(status_code=403, message="Unknown captcha_type")
    
    html: str = await jinja2.render(path=captchas[data['type']]['template'], **context)
    await redis.zincrby(name="IPSTATS:CAPTCHA:GENERATED", amount=1, value=r.ip)

    captchas['stats'][f"captcha{captcha_type}_rendered"] = \
        int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_rendered"))
    return ResponseHTML(content=html)
    
@app.route("/captcha/validate", methods=['POST'])
async def web_validate_captcha(r: Request) -> Response:
    validation: dict = { 'status' : False }
    post: dict[str, str] = r.post

    try:
        if not post.keys() >= {'captcha_id', 'captcha_type', 'hash', 'timestamp', 'sitekey'}:
            raise ValueError("missing parameters")
        
        captcha_type: int = int(post['captcha_type'])

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

    except Exception as e:
        validation['error'] = str(object=e)

    finally:
        if 'error' in validation:
            await redis.zincrby(name="STATS:CAPTCHA:FAILED", amount=1, value=post['sitekey'])
            await redis.zincrby(name="IPSTATS:CAPTCHA:FAILED", amount=1, value=r.ip)
            captchas['stats'][f"captcha{captcha_type}_validations_failed"] = \
                int(await redis.zincrby(name="STATS:GENERAL", amount=1, value=f"captcha{captcha_type}_failed"))
            return ResponseJSON(content=validation)

        result_token: str = utils.FastHash(input=f"{post['sitekey']}__{app.cfg.name}_{post['captcha_id']}")
        await redis.set(name=f"captcha_result_{result_token}", value=json.dumps(obj={
            "ip" : r.ip,
            "captcha_type" : captcha_type,
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

    return ResponseJSON(content=r.post)

app.on_startup(fn=utils.PrepareDataset)
app.on_startup(fn=EnsureCaptchaAvailability)
app.on_startup(fn=LoadStats)