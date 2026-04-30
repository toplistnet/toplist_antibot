from PIL import Image
import random
import base64
from io import BytesIO
from copy import copy
import app.tools.utils as utils
import json
import math

TOLLERENCE: int = int(utils.Config(key='captcha2_tollerance', default="3"))
VERSION: int = 1  # bump when Generate() output schema/semantics change → invalidates redis pool
        
def Generate() -> dict[str, str | int | dict]:
    bgs: list[str] = utils.Cached_Glob(pattern="res/bgs/*/*/*/*/*/*/*")
    bg = utils.GenerateBG(path=random.choice(seq=bgs))
    
    icon: Image.Image = utils.GenerateCircleIcon()
    icon_fake: Image.Image = utils.GenerateCircleIcon()
                
    icon_coordinates: list[dict] = []
    for i in range(int(utils.Config(key='captcha2_icon_count', default="8"))):
        is_fake: bool = i > 0
        icon_to_paste: Image.Image = icon if not is_fake else copy(icon_fake)
 
        CAPTCHA2_MODIFIER = int(utils.Config(key='captcha2_modifier', default="10"))

        # transparency
        icon_to_paste_alpha: Image.Image = icon_to_paste.copy()
        icon_to_paste_alpha.putalpha(alpha=random.randint(a=220, b=255))
        # alter color schema
        color: str = random.choice(seq=['yellow', 'blue', 'purple', 'gray', 'black', 'white'])
        layer: Image.Image = Image.new(mode='RGBA', size=icon_to_paste_alpha.size, color=color) # type: ignore
        icon_to_paste_alpha = Image.blend(im1=icon_to_paste_alpha, im2=layer, alpha=random.randint(a=0, b=CAPTCHA2_MODIFIER) / 100.0)
        icon_to_paste.paste(im=icon_to_paste_alpha, box=icon_to_paste)
        # rotate
        if is_fake:
            icon_to_paste = icon_to_paste.rotate(angle=random.randint(a=-CAPTCHA2_MODIFIER, b=CAPTCHA2_MODIFIER), 
                                                 resample=Image.Resampling.BICUBIC, 
                                                 expand=True)
            
        d: int = max(icon.width, icon.height)
        r: int = math.ceil(d / 2)
    
        newCoords: list[int] = []
        retries = 0
        while not newCoords:
            x: int = random.randint(a=0, b=bg.width - d)
            y: int = random.randint(a=0, b=bg.height - d)

            if not len(icon_coordinates):
                newCoords = [x, y]
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
                    newCoords = [x, y]
                else:
                    retries += 1
                    if retries >= 300:
                        utils.dprint("Captcha 2 Error: Reached max retries")
                        return { 'status' : False, 'error' : 'Error, captcha2 not placed_successfully' }

            if newCoords:
                icon_coordinates.append({'x' : x, 'y' : y, 'r' : r})
                bg.paste(im=icon_to_paste, box=(x, y), mask=icon_to_paste)

    # fix off-center
    icon_coordinates[0]['x'] += icon_coordinates[0]['r']
    icon_coordinates[0]['y'] += icon_coordinates[0]['r']

    bg: Image.Image = bg.convert(mode='RGB')
    if __name__ == '__main__':
        bg.putpixel(xy=(icon_coordinates[0]['x'], icon_coordinates[0]['y']), value=(255, 0, 0))
        bg.save("out.jpg")
        bg.show()
        
    buffered = BytesIO()
    bg.save(buffered, format="JPEG")
    bg_base64_bytes: bytes = base64.b64encode(s=buffered.getvalue())
    bg_base64: str = "data:image/jpeg;base64," + bg_base64_bytes.decode(encoding='utf-8')
    
    return { 
        'status' : True,
        'type' : 2,
        'bg_base64' : bg_base64, 
        'data' : icon_coordinates[0],
    }

def Validate(db_data: dict, post_data: dict) -> None:
    if not post_data.keys() >= {'click'}:
        utils.dprint(f"[captcha2] missing 'click' in post_data; keys={list(post_data.keys())}")
        raise ValueError("missing parameters")

    post_data['click'] = json.loads(s=post_data['click'])

    if len(post_data['click']) != 2:
        utils.dprint(f"[captcha2] click malformed: {post_data['click']}")
        raise ValueError('click must be a list of 2 numbers')

    post_data['click'][0] = round(number=post_data['click'][0])
    post_data['click'][1] = round(number=post_data['click'][1])

    cx: int = db_data['x']
    cy: int = db_data['y']
    cr: int = db_data['r']
    px: int = post_data['click'][0]
    py: int = post_data['click'][1]
    import math
    dist: float = math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
    hit: bool = dist <= cr
    utils.dprint(f"[captcha2] click {'HIT ' if hit else 'MISS'} click=({px},{py}) "
                 f"circle=(x={cx},y={cy},r={cr}) dist={dist:.2f} off={dist - cr:.2f}")
    if not hit:
        raise ValueError('failed')

if __name__ == '__main__':
    utils.PrepareDataset()
    print(Generate())
