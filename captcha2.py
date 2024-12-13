from PIL import Image
import random
import base64
from io import BytesIO
from copy import copy
import utils
from flask import render_template
import db
import json
from localization import Localization
from time import sleep,strftime
from queue import Queue
import numpy as np
import math

TOLLERENCE = utils.Config(key='captcha2_tollerance', default=3)
READY_CAPTCHAS_QUEUE = Queue(maxsize=utils.Config(key='captcha2_pregeneration_count', default=100))

def GenerateBG(path):
    # TODO: cache opening of bgs (30% of generation performance)
    with Image.open(path) as img:
        img = img.convert(mode='RGBA')
        resize = random.randint(a=4, b=11)
        img = img.resize((int(img.width/resize), int(img.height/resize)))
        img = img.resize(size=(300, 300), resample=Image.NEAREST)
        
        layer = Image.new('RGBA', size=img.size, color=random.choice(seq=['blue', 'purple', 'gray', 'black', 'white']))
        img = Image.blend(im1=img, im2=layer, alpha=random.randint(a=15, b=50) / 100.0)
    
        return img                 
        
def GenerateCircleIcon() -> Image:
    im = utils.ICON_DATASET[random.randint(0, len(utils.ICON_DATASET) - 1), :]
    im_r = im[0:1024].reshape(32, 32)
    im_g = im[1024:2048].reshape(32, 32)
    im_b = im[2048:].reshape(32, 32)
    img = np.dstack((im_r, im_g, im_b))
    img = Image.fromarray(obj=img)
    img = utils.CropCircle(img=img, 
                        resize=(img.width + random.randint(a=8, b=30), 
                        img.height + random.randint(a=8, b=30)))
    return img
        
def GenerateCaptcha():
    bgs = utils.Cached_Glob(pattern="res/bgs/*/*/*/*/*/*/*")
    bg = GenerateBG(path=random.choice(seq=bgs))
    
    icon = GenerateCircleIcon()
    icon_fake = GenerateCircleIcon()
                
    icon_coordinates = []
    for i in range(utils.Config(key='captcha2_icon_count', default="8")):
        is_fake = i > 0
        icon_to_paste = icon if not is_fake else copy(icon_fake)
 
        CAPTCHA2_MODIFIER = int(utils.Config(key='captcha2_modifier', default="10"))

        # transparency
        icon_to_paste_alpha = icon_to_paste.copy()
        icon_to_paste_alpha.putalpha(random.randint(220, 255))
        # alter color schema
        layer = Image.new('RGBA', icon_to_paste_alpha.size, random.choice(['yellow', 'blue', 'purple', 'gray', 'black', 'white']))
        icon_to_paste_alpha = Image.blend(icon_to_paste_alpha, layer, random.randint(0, CAPTCHA2_MODIFIER) / 100.0)
        icon_to_paste.paste(icon_to_paste_alpha, icon_to_paste)
        # rotate
        if is_fake:
            icon_to_paste = icon_to_paste.rotate(random.randint(-CAPTCHA2_MODIFIER, CAPTCHA2_MODIFIER), resample=Image.BICUBIC, expand=True)
            
        d = max(icon.width, icon.height)
        r = math.ceil(d / 2)
    
        newCoords = None
        retries = 0
        while newCoords == None:
            x = random.randint(a=0, b=bg.width - d)
            y = random.randint(a=0, b=bg.height - d)

            if not len(icon_coordinates):
                newCoords = x, y
            else:
                any_collision = False
                for c in icon_coordinates:
                    if utils.IsRectCollision(r1x=x - TOLLERENCE, r1y=y - TOLLERENCE, 
                                       r1w=d + TOLLERENCE, r1h=d + TOLLERENCE, 
                                        r2x=c['x'] - TOLLERENCE, 
                                        r2y=c['y'] - TOLLERENCE, 
                                        r2w=d + TOLLERENCE, 
                                        r2h=d + TOLLERENCE):
                        any_collision = True
                        break
                if not any_collision:
                    newCoords: tuple[int, int] = x, y
                else:
                    retries += 1
                    if retries >= 60:
                        if int(utils.Config(key='debug', default=0)):
                            print("Error: Reached max retries")
                        return None

            if newCoords:
                icon_coordinates.append({'x' : x, 'y' : y, 'r' : r})
                bg.paste(im=icon_to_paste, box=(x, y), mask=icon_to_paste)

    bg = bg.convert('RGB')
    if __name__ == '__main__':
        bg.save("out.jpg")
        
    buffered = BytesIO()
    bg.save(buffered, format="JPEG")
    bg_base64 = base64.b64encode(buffered.getvalue())
    bg_base64 = "data:image/jpeg;base64," + bg_base64.decode(encoding='utf-8')
    
    return { 'bg_base64' : bg_base64, 'data' : icon_coordinates[0] }

def Thread_PreGenerateCaptchas2() -> None:
    if not utils.Config(key='captcha2_pregeneration_count', default="100"):
        return
    
    while True:
        while not READY_CAPTCHAS_QUEUE.full():
            if int(utils.Config(key='debug')):
                print(f"{strftime('%Y-%m-%d %H:%M:%S')} generate<2> +1/{READY_CAPTCHAS_QUEUE.qsize()}")
            captcha: dict = GenerateCaptcha()
            if captcha != None:
                READY_CAPTCHAS_QUEUE.put(item=captcha)
        sleep(0.005)
        
def Generate(post_data: dict, forward_url: str) -> dict:
    captcha = READY_CAPTCHAS_QUEUE.get(block = True)
    READY_CAPTCHAS_QUEUE.task_done()
    
    captcha['data']['x'] += captcha['data']['r']
    captcha['data']['y'] += captcha['data']['r']
    
    id: int = db.GetNewCaptchaID()
    data: str = json.dumps(obj=captcha['data'])
    db.SetCaptchaData(id=id, data=str(object=data))
    
    translate = Localization().Translate
    
    html = render_template(template_name_or_list="2/index.html", 
                        post_data = post_data,
                        id = id,
                        captcha = 'findone',
                        img = captcha['bg_base64'],
                        forward_url = forward_url,
                        translate = translate,
                        Config = utils.Config)
    
    return { 'id' : id, 'html' : html, 'data' : captcha['data'] }

def Validate(post_data: dict, is_test: bool) -> dict:
    try:
        data: str = db.GetCaptchaData(id=int(post_data['id']), is_test=is_test)
        
        if not data:
            return { 'status' : False, 'error' : 'NOTFOUND' }
        
        db_data: dict = json.loads(s=data)
        post_data['click'] = json.loads(s=post_data['click'])
        
        if len(post_data['click']) != 2:
            return { 'status' : False, 'error' : 'MISM', 'db' : len(db_data), 'c' : len(post_data['click']) }
         
        post_data['click'][0] = round(number=post_data['click'][0])
        post_data['click'][1] = round(number=post_data['click'][1])

        if not utils.IsPointInCircle(point_circle_center=utils.Point(x=db_data['x'], y=db_data['y']), 
                               point_click=utils.Point(x=post_data['click'][0], y=post_data['click'][1]),
                               radius=db_data['r']):
            if int(utils.Config(key='debug')):
                print(f"USER ERR:    click not in {post_data['click']} | {db_data}")
            return { 'status' : False, 'error' : 'CLICK' }
        
        return { 'status' : True, 'error' : None }
    
    except Exception as e:
        print(utils.stacktrace())
        print("EXCEPTION %s" % str(object=e))
        return { 'status' : False, 'error' : 'Exception' }

if __name__ == '__main__':
    utils.PrepareDataset()
    GenerateCaptcha()