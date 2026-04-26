from app.app import app, redis, db
from muffin import Request, Response, ResponseJSON
import app.tools.utils as utils
import time
import json

@app.route(*("/captcha/api/siteverify", "/recaptcha/api/siteverify"), methods=['POST'])
async def route_captcha_api_siteverify(r: Request) -> Response:
    ip: str = ""
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
        
        b_captcha_result_data = await redis.getdel(name=f"captcha_result_{r.post['response']}") or b''
        captcha_result_data: str = ""
        if type(b_captcha_result_data) == bytes:
            captcha_result_data = b_captcha_result_data.decode()
        elif type(b_captcha_result_data) == str:
            captcha_result_data = b_captcha_result_data

        if not len(captcha_result_data):
            await redis.zincrby(name="STATS:VALIDATION:FAILED", amount=1, value=r.post['secret'])
            raise ValueError("invalid-input-response")
        
        captcha_result: dict = json.loads(s=captcha_result_data)
        ip = captcha_result['remoteip']

        if 'extra' in r.post:
            response['captcha_type'] = captcha_result['captcha_type']
            response['duration'] = captcha_result.get('duration', 0)

        if 'remoteip' in r.post:
            response['remoteip'] = r.post['remoteip'] == ip
        
        await redis.zincrby(name="IPSTATS:VALIDATION:SUCCESS", amount=1, value=ip)
        await redis.zincrby(name="STATS:VALIDATION:SUCCESS", amount=1, value=r.post['secret'])
        # TODO: risk score calculation
        response["success"] = True

    except ValueError as e:
        response['error-codes'].append(str(object=e))

    finally:
        if 'remoteip' in r.post and 'remoteip' not in response:
            response['remoteip'] = False

        if 'extra' in r.post:
            response['captcha_type'] = int(response.get('captcha_type', 0))
            response['duration'] = float(response.get('duration', 0) or 0)

            captchas = await redis.zscore(name="IPSTATS:CAPTCHA:GENERATED", value=ip) or 0
            response['captchas'] = int(captchas)
            valid = await redis.zscore(name="IPSTATS:VALIDATION:SUCCESS", value=ip) or 0
            response['valid'] = int(valid)
            invalid = await redis.zscore(name="IPSTATS:CAPTCHA:FAILED", value=ip) or 0
            response['invalid'] = int(invalid)

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
            'success' : int(await redis.zscore(name="STATS:CAPTCHA:SUCCESS", value=data['sitekey']) or 0),
            'failed' : int(await redis.zscore(name="STATS:CAPTCHA:FAILED", value=data['sitekey']) or 0),
        },
        'validations' : {
            'success' : int(await redis.zscore(name="STATS:VALIDATION:SUCCESS", value=data['secretkey']) or 0),
            'failed' : int(await redis.zscore(name="STATS:VALIDATION:FAILED", value=data['secretkey']) or 0),
        },
        'hosts' : list(await redis.smembers(name=f"HOSTS:{r.post['captcha_user_id']}")),
    }

    return ResponseJSON(content=stats)
