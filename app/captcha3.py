from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import random
import base64
from io import BytesIO
from copy import copy
from app.tools.utils import *
import json
from app.app import redis

TOLLERENCE: int = int(Config(key='captcha3_tollerance', default="10"))
VERSION: int = 3  # bump when Generate() output schema/semantics change → invalidates redis pool

def _TransformBackground(bg: Image.Image) -> Image.Image:
    w, h = bg.size

    # mirror / flip
    if random.random() < 0.5:
        bg = ImageOps.mirror(image=bg)
    if random.random() < 0.15:
        bg = ImageOps.flip(image=bg)

    # rotation (corners filled — masked by the zoom-crop below)
    angle: float = random.uniform(a=-10.0, b=10.0)
    rotated_applied: bool = abs(angle) > 0.1
    if rotated_applied:
        bg = bg.rotate(angle=angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(0, 0, 0))

    # zoom-in (also masks rotation corners; min scales with the absolute angle so corners stay hidden)
    zoom_min: float = 1.00 + abs(angle) * 0.018 if rotated_applied else 1.00
    zoom: float = random.uniform(a=zoom_min, b=max(1.25, zoom_min + 0.05))
    if zoom > 1.01:
        crop_w: int = int(w / zoom)
        crop_h: int = int(h / zoom)
        # random offset only when no rotation, otherwise center to keep corners hidden
        if rotated_applied:
            offx: int = (w - crop_w) // 2
            offy: int = (h - crop_h) // 2
        else:
            offx = random.randint(a=0, b=w - crop_w)
            offy = random.randint(a=0, b=h - crop_h)
        bg = bg.crop(box=(offx, offy, offx + crop_w, offy + crop_h)).resize(size=(w, h), resample=Image.Resampling.LANCZOS)

    # tone (task is shape-based so safe for color-blind users)
    bg = ImageEnhance.Brightness(image=bg).enhance(factor=random.uniform(a=0.85, b=1.15))
    bg = ImageEnhance.Contrast(image=bg).enhance(factor=random.uniform(a=0.85, b=1.30))
    bg = ImageEnhance.Color(image=bg).enhance(factor=random.uniform(a=0.45, b=1.35))
    bg = ImageEnhance.Sharpness(image=bg).enhance(factor=random.uniform(a=0.65, b=1.60))

    # occasional mild blur — softens icon edges into the bg
    if random.random() < 0.15:
        bg = bg.filter(filter=ImageFilter.GaussianBlur(radius=random.uniform(a=0.5, b=1.2)))

    # occasional posterize — collapses color palette
    if random.random() < 0.12:
        bg = ImageOps.posterize(image=bg, bits=random.randint(a=4, b=6))

    # occasional full desaturation — strips hue cues entirely
    if random.random() < 0.18:
        bg = ImageOps.grayscale(image=bg).convert(mode="RGB")

    return bg

def PlaceOneIcon(bg: Image.Image, icon: Image.Image, icon_coordinates: list, icon_collection_img: Image.Image, fake: bool) -> bool:
    newCoords: list[int] = []

    # resize icon (slightly smaller range than captcha1)
    resize_factor: float = random.randint(a=11, b=17) / 10.0
    icon_altered: Image.Image = icon.resize(size=(int(icon.width * resize_factor), int(icon.height * resize_factor)), resample=Image.Resampling.LANCZOS)
    # transparency (a touch more transparent than captcha1)
    icon_altered_alpha: Image.Image = icon_altered.copy()
    icon_altered_alpha.putalpha(random.randint(a=100, b=170))
    # alter color schema (wider palette than captcha1, similar blend strength)
    color: str = random.choice(seq=['yellow', 'blue', 'purple', 'red', 'green', 'orange', 'cyan'])
    layer: Image.Image = Image.new(mode='RGBA', size=icon_altered_alpha.size, color=color) # type: ignore
    icon_altered_alpha = Image.blend(im1=icon_altered_alpha, im2=layer, alpha=random.randint(a=25, b=55) / 100.0)
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
                if retries >= 600:
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
    icons_count: int = random.randint(a=4, b=min(5, len(all_icons)))
    fake_icons_count: int = random.randint(a=1, b=min(2, max(1, len(all_icons) - icons_count)))
    icons_img: Image.Image = Image.new(mode="RGBA", size=(icons_count * 25 - 5, 20), color=(255,255,255,0)) # type: ignore
    all_icons_shuffled: list[str] = copy(all_icons)
    random.shuffle(all_icons_shuffled)
    icons: list[str] = all_icons_shuffled[:icons_count + fake_icons_count]
    icon_coordinates: list[int] = []

    bg: Image.Image = copy(GetCachedPILImage(path=bg_img_path, convert='RGB'))
    bg = _TransformBackground(bg=bg)
    for i, icon_path in enumerate(iterable=icons):
        icon: Image.Image = copy(GetCachedPILImage(path=icon_path, convert='RGBA'))
        placed_successfully: bool = PlaceOneIcon(bg=bg, icon=icon, icon_coordinates=icon_coordinates,
                                           icon_collection_img=icons_img, fake=i >= icons_count)
        if not placed_successfully:
            dprint("Error, captcha3 not placed_successfully")
            dprint(f"{bg} {icons} {icon}")
            return { 'status' : False, 'error' : 'Error, captcha3 not placed_successfully' }

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
            'type' : 3,
            'bg_base64' : bg_base64,
            'icons_base64' : icons_base64,
            'icons_count' : icons_count,
            'icon_coordinates' : icon_coordinates,
            }

def CheckClick(db_data: list, index: int, x: int, y: int) -> bool:
    if index < 0 or index >= len(db_data):
        return False
    rect_data: dict = db_data[index]
    rect = Rectangle(posn=Point(x=rect_data['x'], y=rect_data['y']),
                     w=rect_data['w'], h=rect_data['h'], padding=TOLLERENCE)
    return rect.IsIn(p=Point(x=x, y=y))

def Validate(db_data: dict, post_data: dict) -> None:
    if not post_data.keys() >= {'clicks'}:
        dprint(f"[captcha3] missing 'clicks' in post_data; keys={list(post_data.keys())}")
        raise ValueError("missing parameters")

    clicks_str: str = post_data['clicks']
    clicks: dict = json.loads(s=clicks_str)

    if len(db_data) != len(clicks):
        dprint(f"[captcha3] click count mismatch: expected={len(db_data)} got={len(clicks)} clicks={clicks} rects={db_data}")
        raise ValueError('click count mismatch')

    misses: list = []
    for index in range(len(db_data)):
        rect_data: dict = db_data[index]
        rect = Rectangle(posn=
                            Point(x=rect_data['x'], y=rect_data['y']),
                            w=rect_data['w'], h=rect_data['h'], padding = TOLLERENCE)
        click_x, click_y = clicks[index][0], clicks[index][1]
        click: Point = Point(x=click_x, y=click_y)
        hit: bool = rect.IsIn(p=click)
        rx, ry, rw, rh = rect.pos.x, rect.pos.y, rect.width, rect.height
        dx: int = 0 if rx < click_x < rx + rw else (rx - click_x if click_x <= rx else click_x - (rx + rw))
        dy: int = 0 if ry < click_y < ry + rh else (ry - click_y if click_y <= ry else click_y - (ry + rh))
        dprint(f"[captcha3] click[{index}] {'HIT ' if hit else 'MISS'} click=({click_x},{click_y}) "
               f"icon_bbox=(x={rect_data['x']},y={rect_data['y']},w={rect_data['w']},h={rect_data['h']}) "
               f"padded=(x={rx},y={ry},w={rw},h={rh}) off=(dx={dx},dy={dy}) tollerance={TOLLERENCE}")
        if not hit:
            misses.append(index)

    if misses:
        dprint(f"[captcha3] FAIL: missed {len(misses)}/{len(db_data)} clicks (indices={misses})")
        raise ValueError('failed')

if __name__ == "__main__":
    print(Generate())
