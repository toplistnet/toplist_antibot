import cachetools.func
import math
import os
import pickle
import warnings
from PIL import Image, ImageDraw
import numpy as np
import xxhash
import re
import json
import random
from copy import copy

class Point(object):
    def __init__(self, x: int, y: int) -> None:
        self.x: int = x
        self.y: int = y

    def __str__(self) -> str:
        return "({},{})".format(self.x, self.y)

class Rectangle(object):
    def __init__(self, posn: Point, w: int, h: int, padding: int = 0) -> None:
        self.pos: Point = posn
        self.pos.x -= padding
        self.pos.y -= padding
        self.width: int = w + padding + padding
        self.height: int = h + padding + padding

    def __str__(self) -> str:
        return "({0},{1},{2})".format(self.pos, self.width, self.height)

    def IsIn(self, p: Point) -> bool:
        return  self.pos.x < p.x and self.pos.x + self.width > p.x and\
                self.pos.y < p.y and self.pos.y + self.height > p.y
                
def IsRectCollision(r1x, r1y, r1w, r1h, r2x, r2y, r2w, r2h) -> bool:
    return r1x + r1w >= r2x and \
        r1x <= r2x + r2w and \
        r1y + r1h >= r2y and \
        r1y <= r2y + r2h

def IsPointInCircle(point_circle_center: Point, point_click: Point, radius: int) -> bool:
    dist: float = math.sqrt((point_circle_center.x - point_click.x) ** 2 + (point_circle_center.y - point_click.y) ** 2)
    return dist <= radius

@cachetools.func.ttl_cache(maxsize=1024, ttl=10*60)
def Config(key, default = '') -> str | int:
    import configparser
    from os.path import isfile
    config = configparser.ConfigParser()
    for file in ['config.cfg', 'config.default.cfg']:
        if isfile(path=file):
            config.read(filenames=file)
            break
    
    v: str = config['DEFAULT'][key] if key in config['DEFAULT'] else default
    return int(v) if str(object=v).isdigit() else v

@cachetools.func.ttl_cache(maxsize=512, ttl=30*60)
def Cached_Glob(pattern) -> list[str]:
    from glob import glob
    return glob(pathname=pattern)
    
def stacktrace() -> str:
    import traceback, sys
    exc = sys.exc_info()[0]
    stack = traceback.extract_stack()[:-1]  # last one would be full_stack()
    if exc is not None:  # i.e. an exception is present
        del stack[-1]       # remove call of full_stack, the printed exception
                            # will contain the caught exception caller instead
    trc = 'Traceback (most recent call last):\n'
    stackstr: str = trc + ''.join(traceback.format_list(extracted_list=stack))
    if exc is not None:
         stackstr += '  ' + traceback.format_exc().lstrip(chars=trc)
    return stackstr

def get_linenumber() -> int:
    from inspect import currentframe
    cf = currentframe()
    return cf.f_back.f_lineno

@cachetools.func.ttl_cache(maxsize=50, ttl=20*60)
def GetCachedPILImage(path: str, convert: str) -> Image.Image:
    im = Image.open(fp=path)
    im = im.convert(convert)
    return im
    
def CropCircle(img: Image.Image, resize: tuple | None) -> Image.Image:
    if resize:
        img = img.resize(size=resize)        
    npImage=np.array(object=img)
    h,w=img.size
    alpha = Image.new(mode='L', size=img.size,color=0)
    draw = ImageDraw.Draw(im=alpha)
    draw.pieslice([0,0,h,w],0,360,fill=255)
    npAlpha = np.array(object=alpha)
    npImage = np.dstack(tup=(npImage,npAlpha))
    img = Image.fromarray(obj=npImage)
    return img

ICON_DATASET: dict = {}
def PrepareDataset() -> None:
    if not (os.path.isdir(s='res/cifar-10-batches-py') or os.path.isfile(path='res/cifar-10-python.tar.gz')):
        os.system(command='wget -c https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz -O res/cifar-10-python.tar.gz')
    
    if not os.path.isdir(s='res/cifar-10-batches-py'):
        print('no dir found so extracting tar.gz \n')
        os.system(command='cd res/ && tar xvzf cifar-10-python.tar.gz && cd ../')
    
    global ICON_DATASET
    with open(file='res/cifar-10-batches-py/data_batch_3', mode='rb') as fo:
        with warnings.catch_warnings():
            warnings.filterwarnings(action='ignore', message=r'.*align=0.*')
            data: dict = pickle.load(file=fo, encoding='bytes')
        ICON_DATASET = data[b'data']
   
    if not (os.path.isdir(s='res/bgs') and os.path.isdir('res/bgs/test_lmdb') and os.path.isfile(path='res/bgs/test_lmdb.zip')):
        if not os.path.isdir(s='res/bgs/'):
            os.mkdir(path='res/bgs/')
        if not os.path.isdir(s='res/bgs/test_lmdb/'):
            os.mkdir(path='res/bgs/test_lmdb/')
        if not os.path.isfile(path='res/bgs/test_lmdb.zip'):
            os.system(command='wget -c http://dl.yf.io/lsun/scenes/test_lmdb.zip -O res/bgs/test_lmdb.zip')
    
    if not os.path.isdir('res/bgs/0'):
        print('no dir found so extracting zip \n')
        os.system(command='cd res/bgs && unzip -o test_lmdb.zip && cd ../../')
        
        db_path: str = 'res/bgs/test_lmdb/'
        out_dir: str = 'res/bgs/'
        flat: bool = False
        limit: int = -1
                
        import lmdb
        print('Exporting', db_path, 'to', out_dir)
        env = lmdb.open(db_path, map_size=1099511627776,
                        max_readers=100, readonly=True)
        count = 0
        with env.begin(write=False) as txn:
            cursor = txn.cursor()
            for key, val in cursor:
                if not flat:
                    image_out_dir: str = os.path.join(out_dir, '/'.join(key.decode('ascii')[:6]))
                else:
                    image_out_dir = out_dir
                if not os.path.exists(path=image_out_dir):
                    os.makedirs(name=image_out_dir)
                image_out_path: str = os.path.join(image_out_dir, key.decode('ascii') + '.webp')
                with open(file=image_out_path, mode='wb') as fp:
                    fp.write(val)
                count += 1
                if count == limit:
                    break
                if count % 1000 == 0:
                    print('Finished', count, 'images')

# g_imgBGs: dict[str, Image.Image] = {}
# def GetCachedBaseBG(path) -> Image.Image:
#     global g_imgBGs
#     if path not in g_imgBGs:
#         g_imgBGs[path] = Image.open(fp=path)
#     return g_imgBGs[path]

def GenerateBG(path) -> Image.Image:
    # img = copy(GetCachedBaseBG(path=path)) # caching those is a bad idea while 5k imgs
    with Image.open(fp=path) as img:
        img: Image.Image = img.convert(mode='RGBA')
        resize: int = random.randint(a=4, b=11)
        img = img.resize((int(img.width/resize), int(img.height/resize)))
        img = img.resize(size=(300, 300), resample=Image.NEAREST) # type: ignore
        color: str = random.choice(seq=['blue', 'purple', 'gray', 'black', 'white'])
        layer: Image.Image = Image.new(mode='RGBA', size=img.size, color=color) # type: ignore
        img = Image.blend(im1=img, im2=layer, alpha=random.randint(a=15, b=50) / 100.0)
        return img                 
        
def GenerateCircleIcon() -> Image.Image:
    global ICON_DATASET
    im = ICON_DATASET[random.randint(a=0, b=len(ICON_DATASET) - 1), :]
    im_r = im[0:1024].reshape(32, 32)
    im_g = im[1024:2048].reshape(32, 32)
    im_b = im[2048:].reshape(32, 32)
    img_array = np.dstack(tup=(im_r, im_g, im_b))
    img: Image.Image = Image.fromarray(obj=img_array)
    return CropCircle(img=img, 
                        resize=(img.width + random.randint(a=8, b=30), 
                        img.height + random.randint(a=8, b=30)))

def FastHash(input: str | int) -> str:
    return xxhash.xxh64(str(object=input)).hexdigest()

def ValidateHosts(input: str) -> set:
    if len(input) > 150:
        return set()
    
    patterns: set = {
        r'^(?=.{1,253}\.?$)(?:(?!-|[^.]+_)[A-Za-z0-9-_]{1,63}(?<!-)(?:\.|$)){2,}$',
r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):\d{1,5}\b', 
    }
    hosts = set()
    for _host in input.split(sep=','):
        for pattern in patterns:
            if re.match(pattern=pattern, string=_host) != None:
                hosts.add(_host.strip())
    return hosts

def dprint(*args, **kwargs) -> None:
    if int(Config(key='debug', default="0")):
        print(*args, **kwargs)

def safe_serialize(obj, html=True, sort_keys=True) -> str:
  _filter = lambda o: f"<{type(o).__qualname__}>"
  _s: str = json.dumps(obj=obj, default=_filter, indent=4)
  if html:
    _s = _s.replace('<', '&lt;').replace('>', '&gt;')
    _s = _s.replace('\n', '<br>').replace(' ', '&nbsp;')
    _s += '''<style>
    body {
        font-family: monospace;
        background-color: #333;
        color: #f0f0f0;
    }
    </style>
    '''
  return _s
