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

READY_CAPTCHAS_QUEUE = Queue(maxsize=Config('captcha1_pregeneration_count', 100))
TOLLERENCE = Config('captcha1_tollerance', 12)

def PlaceOneIcon(bg: Image.Image, icon: Image.Image, icon_coordinates: list, icon_index: int, icon_collection_img: Image.Image, fake: bool) -> bool:
    newCoords = None
    
    # resize icon
    resize_factor = random.randint(11, 18) / 10.0
    icon_altered = icon.resize((int(icon.width * resize_factor), int(icon.height * resize_factor)), resample=Image.LANCZOS)
    # transparency
    icon_altered_alpha = icon_altered.copy()
    icon_altered_alpha.putalpha(random.randint(85, 160))
    # alter color schema
    layer = Image.new('RGBA', icon_altered_alpha.size, random.choice(['yellow', 'blue', 'purple']))
    icon_altered_alpha = Image.blend(icon_altered_alpha, layer, random.randint(20, 60) / 100.0)
    icon_altered.paste(icon_altered_alpha, icon_altered)
    # rotate
    icon_altered = icon_altered.rotate(random.randint(-180, 180), resample=Image.BICUBIC, expand=True)
    
    retries = 0
    while newCoords == None:
        x = random.randint(TOLLERENCE, bg.width - icon_altered.width - TOLLERENCE)
        y = random.randint(TOLLERENCE, bg.height - icon_altered.height - TOLLERENCE)

        if not len(icon_coordinates):
            newCoords = x, y
        else:
            any_collision = False
            for c in icon_coordinates:
                if IsRectCollision(x - TOLLERENCE, y - TOLLERENCE, icon_altered.width + TOLLERENCE, icon_altered.height + TOLLERENCE, \
                                        c['x'] - TOLLERENCE, c['y'] - TOLLERENCE, c['w'] + TOLLERENCE, c['h'] + TOLLERENCE):
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
        icon_collection_img.paste(icon, (len(icon_coordinates)*25, 0))
        icon_coordinates.append({'x' : x, 'y' : y, 'w' : icon_altered.width, 'h' : icon_altered.height})
  
    bg.paste(icon_altered, newCoords, icon_altered)
    return True

def GenerateCaptcha() -> any:
    all_icons = Cached_Glob('res/1/icons/*')
    bg_img_path = random.choice(Cached_Glob('res/1/bgs/*'))
    icons_count = random.randint(3, min(4, len(all_icons)))
    fake_icons_count = random.randint(0, 1)
    icons_img = Image.new("RGBA", (icons_count * 25 - 5, 20), (255,255,255,0))
    all_icons_shuffled = copy(all_icons)
    random.shuffle(all_icons_shuffled)
    icons = all_icons_shuffled[:icons_count + fake_icons_count]
    fake_icon = all_icons_shuffled[icons_count + fake_icons_count - 1] if fake_icons_count else None
    icon_coordinates = []
    
    bg = copy(GetCachedPILImage(bg_img_path, 'RGB'))
    for icon_path in icons:
        icon = copy(GetCachedPILImage(icon_path, 'RGBA'))
        placed_successfully = PlaceOneIcon(bg, icon, icon_coordinates, all_icons.index(icon_path), icons_img, fake=fake_icon == icon_path)
        if not placed_successfully:
            return None
        
    buffered = BytesIO()
    bg.save(buffered, format="JPEG")
    bg_base64 = base64.b64encode(buffered.getvalue())
    bg_base64 = "data:image/jpeg;base64," + bg_base64.decode('utf-8')
    
    buffered = BytesIO()
    icons_img.save(buffered, format="PNG")
    icons_base64 = base64.b64encode(buffered.getvalue())
    icons_base64 = "data:image/png;base64," + icons_base64.decode('utf-8')
    
    if __name__ == "__main__":
        bg.save("test.jpeg", "JPEG")
        icons_img.save("test_icons.png", "PNG")
        bg.show()
        icons_img.show()
        
    return { 'bg_base64' : bg_base64, 'icons_base64' : icons_base64, 'icons_count' : icons_count, 'icon_coordinates' : icon_coordinates }

def Thread_PreGenerateCaptchas1():
    if not Config('captcha1_pregeneration_count', 100):
        return
    
    while True:
        while not READY_CAPTCHAS_QUEUE.full():
            if Config('debug'):
                print(f"{strftime('%Y-%m-%d %H:%M:%S')} generate<1> +1/{READY_CAPTCHAS_QUEUE.qsize()}")
            captcha = GenerateCaptcha()
            if captcha != None:
                READY_CAPTCHAS_QUEUE.put(captcha)
        sleep(0.005)
        
def Generate(post_data: dict, forward_url: str) -> dict:
    captcha = READY_CAPTCHAS_QUEUE.get(block = True)
    READY_CAPTCHAS_QUEUE.task_done()
    
    id = db.GetNewCaptchaID()
    data = json.dumps(captcha['icon_coordinates'])
    db.SetCaptchaData(id, str(data))
    
    translate = Localization().Translate
    
    html = render_template("1/index.html", 
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
        data = db.GetCaptchaData(int(post_data['id']), is_test)
        
        if not data:
            return { 'status' : False, 'error' : 'NOTFOUND' }
        
        db_data = json.loads(data)
        post_data['clicks'] = json.loads(post_data['clicks'])

        if len(db_data) != len(post_data['clicks']):
            if len(db_data) < len(post_data['clicks']):
                return { 'status' : False, 'error' : 'TOOMANY' }
            
            if is_test:
                index = len(post_data['clicks']) - 1
                rect_data = db_data[index]
                rect = Rectangle(Point(rect_data['x'], rect_data['y']), rect_data['w'], rect_data['h'], padding = TOLLERENCE)
                result = rect.IsIn(Point(post_data['clicks'][index][0], post_data['clicks'][index][1]))
                
                Stats().Add(post_data['server_id'], Stats.what.valid_tests if result else Stats.what.invalid_tests)
                
                if not result and Config('debug'):
                    print("USER ERR:    click[%d] not in %s | %s | %s" % (index, str(post_data['clicks'][index]), str(rect_data), str(rect)))
                elif Config('debug'):
                    print("OKOK OKK:    click[%d] not in %s | %s | %s" % (index, str(post_data['clicks'][index]), str(rect_data), str(rect)))
                return { 'status' : result }
            
            return { 'status' : False, 'error' : 'MISM', 'db' : len(db_data), 'c' : len(post_data['clicks']) }
        
        index = 0
        for rect_data in db_data:
            rect = Rectangle(Point(rect_data['x'], rect_data['y']), rect_data['w'], rect_data['h'], padding = TOLLERENCE)
            
            if not rect.IsIn(Point(post_data['clicks'][index][0], post_data['clicks'][index][1])):
                if Config('debug'):
                    print("USER ERR:    click[%d] not in %s | %s | %s" % (index, str(post_data['clicks'][index]), str(rect_data), str(rect)))
                return { 'status' : False, 'error' : 'CLICK' + str(index) }
            
            index += 1
        
        return { 'status' : True, 'error' : None }
    except Exception as e:
        print(stacktrace())
        print("EXCEPTION %s" % str(e))
        return { 'status' : False, 'error' : 'Exception' }

if __name__ == "__main__":
    res = Generate({}, '')
    print(res)