from PIL import Image
import random
import base64
from io import BytesIO
from copy import copy
from utils import *
from flask import render_template
import db
import json
from localization import Localization
from stats import Stats
from time import sleep,strftime
from queue import Queue

READY_CAPTCHAS_QUEUE = Queue(maxsize=int(Config(key='captcha1_pregeneration_count', default="100")))
TOLLERENCE: int = int(Config(key='captcha1_tollerance', default="12"))

def PlaceOneIcon(bg: Image.Image, icon: Image.Image, icon_coordinates: list, icon_index: int, icon_collection_img: Image.Image, fake: bool) -> bool:
    newCoords = None
    
    # resize icon
    resize_factor: float = random.randint(a=11, b=18) / 10.0
    icon_altered = icon.resize(size=(int(icon.width * resize_factor), int(icon.height * resize_factor)), resample=Image.LANCZOS)
    # transparency
    icon_altered_alpha = icon_altered.copy()
    icon_altered_alpha.putalpha(random.randint(a=85, b=160))
    # alter color schema
    layer = Image.new(mode='RGBA', size=icon_altered_alpha.size, color=random.choice(seq=['yellow', 'blue', 'purple']))
    icon_altered_alpha = Image.blend(im1=icon_altered_alpha, im2=layer, alpha=random.randint(a=20, b=60) / 100.0)
    icon_altered.paste(icon_altered_alpha, icon_altered)
    # rotate
    icon_altered = icon_altered.rotate(random.randint(a=-180, b=180), resample=Image.BICUBIC, expand=True)
    
    retries = 0
    while newCoords == None:
        x: int = random.randint(a=TOLLERENCE, b=bg.width - icon_altered.width - TOLLERENCE)
        y: int = random.randint(a=TOLLERENCE, b=bg.height - icon_altered.height - TOLLERENCE)

        if not len(icon_coordinates):
            newCoords = x, y
        else:
            any_collision = False
            for c in icon_coordinates:
                if IsRectCollision(r1x=x - TOLLERENCE, r1y=y - TOLLERENCE, r1w=icon_altered.width + TOLLERENCE, r1h=icon_altered.height + TOLLERENCE, \
                                        r2x=c['x'] - TOLLERENCE, r2y=c['y'] - TOLLERENCE, r2w=c['w'] + TOLLERENCE, r2h=c['h'] + TOLLERENCE):
                    any_collision = True
                    break
            if not any_collision:
                    newCoords = x, y
            else:
                retries += 1
                if retries >= 20:
                    return False
        
    if not fake: # as the fake icon is last always, no extra checks for collisions/exclusion
        x, y = newCoords
        icon_collection_img.paste(im=icon, box=(len(icon_coordinates)*25, 0))
        icon_coordinates.append({'x' : x, 'y' : y, 'w' : icon_altered.width, 'h' : icon_altered.height})
  
    bg.paste(im=icon_altered, box=newCoords, mask=icon_altered)
    return True

def GenerateCaptcha():
    all_icons = Cached_Glob(pattern='res/1/icons/*')
    bg_img_path = random.choice(seq=Cached_Glob(pattern='res/1/bgs/*'))
    icons_count: int = random.randint(a=3, b=min(4, len(all_icons)))
    fake_icons_count = random.randint(a=0, b=1)
    icons_img = Image.new(mode="RGBA", size=(icons_count * 25 - 5, 20), color=(255,255,255,0))
    all_icons_shuffled = copy(all_icons)
    random.shuffle(all_icons_shuffled)
    icons = all_icons_shuffled[:icons_count + fake_icons_count]
    fake_icon = all_icons_shuffled[icons_count + fake_icons_count - 1] if fake_icons_count else None
    icon_coordinates = []
    
    bg = copy(GetCachedPILImage(path=bg_img_path, convert='RGB'))
    for icon_path in icons:
        icon = copy(GetCachedPILImage(path=icon_path, convert='RGBA'))
        placed_successfully: bool = PlaceOneIcon(bg=bg, icon=icon, icon_coordinates=icon_coordinates, 
                                           icon_index=all_icons.index(icon_path), 
                                           icon_collection_img=icons_img, fake=fake_icon == icon_path)
        if not placed_successfully:
            return None
        
    buffered = BytesIO()
    bg.save(buffered, format="JPEG")
    bg_base64 = base64.b64encode(buffered.getvalue())
    bg_base64 = "data:image/jpeg;base64," + bg_base64.decode(encoding='utf-8')
    
    buffered = BytesIO()
    icons_img.save(fp=buffered, format="PNG")
    icons_base64 = base64.b64encode(buffered.getvalue())
    icons_base64 = "data:image/png;base64," + icons_base64.decode(encoding='utf-8')
    
    if __name__ == "__main__":
        bg.save("test.jpeg", "JPEG")
        icons_img.save(fp="test_icons.png", format="PNG")
        bg.show()
        icons_img.show()
        
    return { 'bg_base64' : bg_base64, 'icons_base64' : icons_base64, 'icons_count' : icons_count, 'icon_coordinates' : icon_coordinates }

def Thread_PreGenerateCaptchas1() -> None:
    if not int(Config(key='captcha1_pregeneration_count', default="100")):
        return
    
    while True:
        while not READY_CAPTCHAS_QUEUE.full():
            if int(Config(key='debug')):
                print(f"{strftime('%Y-%m-%d %H:%M:%S')} generate<1> +1/{READY_CAPTCHAS_QUEUE.qsize()}")
            captcha = GenerateCaptcha()
            if captcha != None:
                READY_CAPTCHAS_QUEUE.put(item=captcha)
        sleep(0.005)
        
def Generate(post_data: dict, forward_url: str) -> dict:
    captcha = READY_CAPTCHAS_QUEUE.get(block = True)
    READY_CAPTCHAS_QUEUE.task_done()
    
    id: int = db.GetNewCaptchaID()
    data: str = json.dumps(obj=captcha['icon_coordinates'])
    db.SetCaptchaData(id=id, data=str(object=data))
    
    translate = Localization().Translate
    
    html = render_template(template_name_or_list="1/index.html", 
                        post_data = post_data,
                        id = id,
                        captcha = 'clickicon',
                        img = captcha['bg_base64'],
                        icons = captcha['icons_base64'],
                        icons_count = captcha['icons_count'],
                        forward_url = forward_url,
                        translate = translate,
                        Config = Config)
    
    return { 'id' : id, 'html' : html, 'icons_internal' : captcha['icon_coordinates'] }

def Validate(post_data: dict, is_test: bool) -> dict:
    try:
        data: str = db.GetCaptchaData(id=int(post_data['id']), is_test=is_test)
        
        if not data:
            return { 'status' : False, 'captcha_type' : 1, 'error' : 'NOTFOUND' }
        
        db_data: dict = json.loads(s=data)
        post_data['clicks'] = json.loads(post_data['clicks'])

        if len(db_data) != len(post_data['clicks']):
            if len(db_data) < len(post_data['clicks']):
                return { 'status' : False, 'captcha_type' : 1, 'error' : 'TOOMANY' }
            
            if is_test:
                index: int = len(post_data['clicks']) - 1
                rect_data = db_data[index]
                rect = Rectangle(posn=Point(x=rect_data['x'], y=rect_data['y']), 
                                 w=rect_data['w'], h=rect_data['h'], padding = TOLLERENCE)
                result: bool = rect.IsIn(Point(post_data['clicks'][index][0], post_data['clicks'][index][1]))
                
                Stats().Add(server_id=post_data['server_id'], what=Stats.what.valid_tests if result else Stats.what.invalid_tests)
                
                if not result and int(Config(key='debug')):
                    print("USER ERR:    click[%d] not in %s | %s | %s" % (index, str(post_data['clicks'][index]), str(object=rect_data), str(object=rect)))
                elif int(Config(key='debug')):
                    print("OKOK OKK:    click[%d] not in %s | %s | %s" % (index, str(post_data['clicks'][index]), str(object=rect_data), str(object=rect)))
                return { 'status' : result, 'captcha_type' : 1 }
            
            return { 'status' : False, 'captcha_type' : 1, 'error' : 'MISM', 'db' : len(db_data), 'c' : len(post_data['clicks']) }
        
        index = 0
        for rect_data in db_data:
            rect = Rectangle(posn=
                             Point(x=rect_data['x'], y=rect_data['y']),
                             w=rect_data['w'], h=rect_data['h'], padding = TOLLERENCE)
            
            if not rect.IsIn(Point(x=post_data['clicks'][index][0], y=post_data['clicks'][index][1])):
                if int(Config(key='debug')):
                    print("USER ERR:    click[%d] not in %s | %s | %s" % (index, str(object=post_data['clicks'][index]), str(object=rect_data), str(rect)))
                return { 'status' : False, 'captcha_type' : 1, 'error' : 'CLICK' + str(object=index) }
            
            index += 1
        
        return { 'status' : True, 'captcha_type' : 1, 'error' : None }
    except Exception as e:
        print(stacktrace())
        print("EXCEPTION %s" % str(object=e))
        return { 'status' : False, 'captcha_type' : 1, 'error' : 'Exception' }

if __name__ == "__main__":
    res = Generate(post_data={}, forward_url='')
    print(res)