from PIL import Image
import random
import base64
from io import BytesIO
from copy import copy
from app.tools.utils import *
import json
from app.app import redis

TOLLERENCE: int = int(Config(key='captcha1_tollerance', default="12"))

def PlaceOneIcon(bg: Image.Image, icon: Image.Image, icon_coordinates: list, icon_collection_img: Image.Image, fake: bool) -> bool:
    newCoords: list[int] = []
    
    # resize icon
    resize_factor: float = random.randint(a=11, b=18) / 10.0
    icon_altered: Image.Image = icon.resize(size=(int(icon.width * resize_factor), int(icon.height * resize_factor)), resample=Image.Resampling.LANCZOS)
    # transparency
    icon_altered_alpha: Image.Image = icon_altered.copy()
    icon_altered_alpha.putalpha(random.randint(a=85, b=160))
    # alter color schema
    color: str = random.choice(seq=['yellow', 'blue', 'purple'])
    layer: Image.Image = Image.new(mode='RGBA', size=icon_altered_alpha.size, color=color) # type: ignore
    icon_altered_alpha = Image.blend(im1=icon_altered_alpha, im2=layer, alpha=random.randint(a=20, b=60) / 100.0)
    icon_altered.paste(icon_altered_alpha, icon_altered)
    # rotate
    icon_altered = icon_altered.rotate(random.randint(a=-180, b=180), resample=Image.Resampling.BICUBIC, expand=True)
    
    retries = 0
    while not newCoords:
        x: int = random.randint(a=TOLLERENCE, b=bg.width - icon_altered.width - TOLLERENCE)
        y: int = random.randint(a=TOLLERENCE, b=bg.height - icon_altered.height - TOLLERENCE)

        if not len(icon_coordinates):
            newCoords = [x, y]
        else:
            any_collision = False
            for c in icon_coordinates:
                if IsRectCollision(r1x=x - TOLLERENCE, r1y=y - TOLLERENCE, r1w=icon_altered.width + TOLLERENCE, r1h=icon_altered.height + TOLLERENCE, \
                                        r2x=c['x'] - TOLLERENCE, r2y=c['y'] - TOLLERENCE, r2w=c['w'] + TOLLERENCE, r2h=c['h'] + TOLLERENCE):
                    any_collision = True
                    break
            if not any_collision:
                    newCoords = [x, y]
            else:
                retries += 1
                if retries >= 400:
                    return False
        
    if not fake: # as the fake icon is last always, no extra checks for collisions/exclusion
        x, y = newCoords
        icon_collection_img.paste(im=icon, box=(len(icon_coordinates)*25, 0))
        icon_coordinates.append({'x' : x, 'y' : y, 'w' : icon_altered.width, 'h' : icon_altered.height})
  
    bg.paste(im=icon_altered, box=newCoords, mask=icon_altered)
    return True

def Generate() -> dict[str, str | int | list]:
    all_icons: list[str] = Cached_Glob(pattern='res/1/icons/*')
    bg_img_path: str = random.choice(seq=Cached_Glob(pattern='res/1/bgs/*'))
    icons_count: int = random.randint(a=3, b=min(4, len(all_icons)))
    fake_icons_count: int = random.randint(a=0, b=1)
    icons_img: Image.Image = Image.new(mode="RGBA", size=(icons_count * 25 - 5, 20), color=(255,255,255,0)) # type: ignore
    all_icons_shuffled: list[str] = copy(all_icons)
    random.shuffle(all_icons_shuffled)
    icons: list[str] = all_icons_shuffled[:icons_count + fake_icons_count]
    fake_icon: str | None = all_icons_shuffled[icons_count + fake_icons_count - 1] if fake_icons_count else None
    icon_coordinates: list[int] = []
    
    bg: Image.Image = copy(GetCachedPILImage(path=bg_img_path, convert='RGB'))
    for icon_path in icons:
        icon: Image.Image = copy(GetCachedPILImage(path=icon_path, convert='RGBA'))
        placed_successfully: bool = PlaceOneIcon(bg=bg, icon=icon, icon_coordinates=icon_coordinates, 
                                           icon_collection_img=icons_img, fake=fake_icon == icon_path)
        if not placed_successfully:
            print("Error, captcha1 not placed_successfully")
            print(f"{bg} {icons} {fake_icon} {icon}")
            return { 'status' : False, 'error' : 'Error, captcha1 not placed_successfully' }
        
    buffered = BytesIO()
    bg.save(fp=buffered, format="JPEG")
    bg_base64_bytes: bytes = base64.b64encode(buffered.getvalue())
    bg_base64: str = "data:image/jpeg;base64," + bg_base64_bytes.decode(encoding='utf-8')
    
    buffered = BytesIO()
    icons_img.save(fp=buffered, format="PNG")
    icons_base64_bytes: bytes = base64.b64encode(buffered.getvalue())
    icons_base64: str = "data:image/png;base64," + icons_base64_bytes.decode(encoding='utf-8')
    
    if __name__ == "__main__":
        bg.save(fp="test.jpeg", format="JPEG")
        icons_img.save(fp="test_icons.png", format="PNG")
        bg.show()
        icons_img.show()
        
    return { 'status' : True,
            'type' : 1,
            'bg_base64' : bg_base64, 
            'icons_base64' : icons_base64, 
            'icons_count' : icons_count, 
            'icon_coordinates' : icon_coordinates,
            }
        
def Validate(db_data: dict, post_data: dict) -> None:
    if not post_data.keys() >= {'clicks'}:
        raise ValueError("missing parameters")
    
    clicks_str: str = post_data['clicks']
    clicks: dict = json.loads(s=clicks_str)
    
    if len(db_data) != len(clicks):
        raise ValueError('click count mismatch')
            
    index = 0
    for index in range(len(db_data)):
        rect_data: dict = db_data[index]
        rect = Rectangle(posn=
                            Point(x=rect_data['x'], y=rect_data['y']),
                            w=rect_data['w'], h=rect_data['h'], padding = TOLLERENCE)
        click: Point = Point(x=clicks[index][0], y=clicks[index][1])
        if not rect.IsIn(p=click):
            if int(Config(key='debug')): # TODO: logging, analyzing
                print(f"USER ERR:    click[{index}] not in {clicks[index]} | {rect_data} | {rect}")

            raise ValueError('failed')
        
        index += 1
    
if __name__ == "__main__":
    print(Generate())
