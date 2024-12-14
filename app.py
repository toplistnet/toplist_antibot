import logging
logging.basicConfig(format='%(asctime)s  %(levelname)s  %(message)s', 
                    filename='log.log', encoding='utf-8', level=logging.DEBUG)
import captcha1
import captcha2
from utils import GetForwardUrl, Config
from flask import Flask, request, redirect, g, make_response
from stats import *
from localization import locale_blueprint

app = Flask(import_name="antibot", template_folder='res')
app.logger.setLevel(level=logging.DEBUG)
app.secret_key = '0d342d4b4ff8c112ab0439bdc775c5706b1fb2e5c511be52f2bfe889dcdfe2ba'
app.register_blueprint(blueprint=stats_blueprint)
app.register_blueprint(blueprint=locale_blueprint)

if Config(key='profiler', default="0") == 'pyinstrument': # suggested
    from pyinstrument import Profiler
    profiler = Profiler()
    profiler.start()
    profiler.stop()
            
@app.route(rule="/captcha", methods=['GET','POST'])
def web_gen_captcha():
    # TODO: add hash to post data, verify post data first (captcha type etc)
    ip: str = ""
    if 'X-Real-IP' not in request.headers:
        request.remote_addr 
    else:
        request.headers.get(key='X-Real-IP', default='x')

    if request.method == 'GET':
        if request.referrer and request.referrer != request.url:
            return redirect(location=request.referrer)
        else:
            return redirect(location=str(object=Config(key='url')))
            
    post: dict[str, str] = request.form.to_dict()
    
    if not post.keys() >= {'voted', 'server_id', 'player_id', '_f', 'locale', 'captcha_type'}:
        return "missing parameters"
    
    Stats().Add(server_id=str(object=post['server_id']), what=Stats.what.captchas)
    IPStats().Add(ip=ip, what=IPStats.what.captchas)
    
    forward_url: str = str(object=GetForwardUrl(url=request.referrer))
    captcha_type: int = int(post['captcha_type'])
    
    if captcha_type == 1:
        captcha1.Generate(post_data=post, forward_url=forward_url).get('html', '')
    elif captcha_type == 2:
        return captcha2.Generate(post_data=post, forward_url=forward_url).get('html', '')
    
    return "not found"

# TODO: replace API call with info in redirect url, and hash to verify 

@app.route("/validate", methods=['POST'])
def web_validate_captcha():
    post: dict[str, str] = request.form.to_dict()
    ip: str = ""
    if 'X-Real-IP' not in request.headers:
        request.remote_addr
    else:
        request.headers.get(key='X-Real-IP', default='127.0.0.1')

    is_test: bool = ip == '127.0.0.1' or 'test' in post
    
    if 'internal' in post:
        ip = post['internal']
    if 'delete' in post:
        is_test = False
    
    if not post.keys() >= {'id', 'captcha'}:
        return "missing parameters0"
    
    Stats().Add(server_id=post['server_id'], what=Stats.what.validations)
    validation = { 'status' : False, 'error' : 'TYPE' }
    
    if post['captcha'] == 'clickicon':
        if not post.keys() >= {'clicks'}:
            return "missing parameters1" + str(object=post)
        validation = captcha1.Validate(post_data=post, is_test=is_test)
    elif post['captcha'] == 'findone':
        if not post.keys() >= {'click'}:
            return "missing parametersk1" + str(object=post)
        validation = captcha2.Validate(post_data=post, is_test=is_test)
    
    if 'internal' in post:
        validation['captchas'] = IPStats().Get(ip=ip, what=IPStats.what.captchas)
        validation['valid'] = IPStats().Get(ip=ip, what=IPStats.what.valid)
        validation['invalid'] = IPStats().Get(ip=ip, what=IPStats.what.invalid)
    else:
        if validation['status']:
            Stats().Add(server_id=post['server_id'], what=Stats.what.valid)
            IPStats().Add(ip=ip, what=IPStats.what.valid)
        else:
            Stats().Add(server_id=post['server_id'], what=Stats.what.invalid)
            IPStats().Add(ip=ip, what=IPStats.what.invalid)
            
    if int(Config(key='debug')) and 'player_id' in post and post['player_id'] == "1":
        print(f"DBG:{ip}:{is_test} {validation}")
        print(f"DBG:{post}")
        
    return validation

if not int(Config(key='debug')):
    @app.errorhandler(code_or_exception=404)
    def page_not_found(e):
        return "",400
    
    @app.errorhandler(Exception)
    def all_exception_handler(error):
        print("%s %s" % (request.url, str(error)))
        return "",500
else:
    @app.route(rule='/test_gen/1')
    def web_test_gen1():
        captcha = captcha1.GenerateCaptcha()
        return ""
    
    @app.route(rule='/test_gen/2')
    def web_test_gen2():
        captcha = captcha2.GenerateCaptcha()
        return ""

if Config(key='profiler', default="0") == 'pyinstrument':
    @app.before_request
    def before_request() -> None:
        if "profile" in request.args:
            g.profiler = Profiler()
            g.profiler.start()

    @app.after_request
    def after_request(response):
        if not hasattr(g, "profiler"):
            return response
        g.profiler.stop()
        output_html = g.profiler.output_text()
        return make_response(output_html)