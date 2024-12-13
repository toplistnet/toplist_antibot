import logging
logging.basicConfig(format='%(asctime)s  %(levelname)s  %(message)s', 
                    filename='log.log', encoding='utf-8', level=logging.DEBUG)

import captcha1
import captcha2
from utils import GetForwardUrl, Config
from flask import Flask, request, redirect, g, make_response
from stats import *
from localization import locale_blueprint

app = Flask("antibot", template_folder='res')
app.logger.setLevel(level=logging.DEBUG)
app.secret_key = '0d342d4b4ff8c112ab0439bdc775c5706b1fb2e5c511be52f2bfe889dcdfe2ba'
app.register_blueprint(stats_blueprint)
app.register_blueprint(locale_blueprint)

if Config('profiler', 0) == 'pyinstrument': # suggested
    from pyinstrument import Profiler
    profiler = Profiler()
    profiler.start()
    profiler.stop()
            
@app.route("/captcha", methods=['GET','POST'])
def web_gen_captcha():
    ip = request.remote_addr if 'X-Real-IP' not in request.headers else request.headers['X-Real-IP']
    if request.method == 'GET':
        if request.referrer and request.referrer != request.url:
            return redirect(request.referrer)
        else:
            return redirect(Config('url'))
            
    post = request.form.to_dict()
    
    if not post.keys() >= {'voted', 'server_id', 'player_id', '_f', 'locale'}:
        return "missing parameters"
    
    Stats().Add(post['server_id'], Stats.what.captchas)
    IPStats().Add(ip, IPStats.what.captchas)
    
    captcha = Config('captcha', 2)
    if captcha == 1:
        captcha = captcha1.Generate(post, GetForwardUrl(request.referrer))
    elif captcha == 2:
        captcha = captcha2.Generate(post, GetForwardUrl(request.referrer))
    return captcha['html']

@app.route("/validate", methods=['POST'])
def web_validate_captcha():
    post = request.form.to_dict()
    ip = request.remote_addr if 'X-Real-IP' not in request.headers else request.headers['X-Real-IP']
    is_test = ip == '127.0.0.1' or 'test' in post
    
    if 'internal' in post:
        ip = post['internal']
    if 'delete' in post:
        is_test = False
    
    if not post.keys() >= {'id', 'captcha'}:
        return "missing parameters0"
    
    Stats().Add(post['server_id'], Stats.what.validations)
    validation = { 'status' : False, 'error' : 'TYPE' }
    
    if post['captcha'] == 'clickicon':
        if not post.keys() >= {'clicks'}:
            return "missing parameters1" + str(post)
        validation = captcha1.Validate(post, is_test)
    elif post['captcha'] == 'findone':
        if not post.keys() >= {'click'}:
            return "missing parametersk1" + str(post)
        validation = captcha2.Validate(post, is_test)
    
    if 'internal' in post:
        validation['captchas'] = IPStats().Get(ip, IPStats.what.captchas)
        validation['valid'] = IPStats().Get(ip, IPStats.what.valid)
        validation['invalid'] = IPStats().Get(ip, IPStats.what.invalid)
    else:
        if validation['status']:
            Stats().Add(post['server_id'], Stats.what.valid)
            IPStats().Add(ip, IPStats.what.valid)
        else:
            Stats().Add(post['server_id'], Stats.what.invalid)
            IPStats().Add(ip, IPStats.what.invalid)
            
    if Config('debug') and 'player_id' in post and post['player_id'] == "1":
        print(f"DBG:{ip}:{is_test} {validation}")
        print(f"DBG:{post}")
        
    return validation

if not Config('debug'):
    @app.errorhandler(404)
    def page_not_found(e):
        return "",400
    
    @app.errorhandler(Exception)
    def all_exception_handler(error):
        print("%s %s" % (request.url, str(error)))
        return "",500
else:
    @app.route('/test_gen')
    def web_test_gen():
        if Config('captcha', 2) == 1:
            captcha = captcha1.GenerateCaptcha()
        elif Config('captcha', 2) == 2:
            captcha = captcha2.GenerateCaptcha()
        return ""

if Config('profiler', 0) == 'pyinstrument':
    @app.before_request
    def before_request():
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