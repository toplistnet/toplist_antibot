import cachetools.func
from PIL import Image
import math
from PIL import Image, ImageDraw
import numpy as np 
import pickle
import os

class Point(object):
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __str__(self):
        return "({},{})".format(self.x, self.y)

class Rectangle(object):
    def __init__(self, posn: Point, w: int, h: int, padding: int = 0):
        self.pos = posn
        self.pos.x -= padding
        self.pos.y -= padding
        self.width = w + padding + padding
        self.height = h + padding + padding

    def __str__(self):
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
    dist = math.sqrt((point_circle_center.x - point_click.x) ** 2 + (point_circle_center.y - point_click.y) ** 2)
    return dist <= radius

@cachetools.func.ttl_cache(maxsize=128, ttl=10*60)
def Config(key, default = '') -> any:
    import configparser
    from os.path import isfile
    config = configparser.ConfigParser()
    for file in ['config.cfg', 'config.default.cfg']:
        if isfile(file):
            config.read(file)
            break
    
    v = config['DEFAULT'][key] if key in config['DEFAULT'] else default
    return int(v) if str(v).isdigit() else v

@cachetools.func.ttl_cache(maxsize=128, ttl=10*60)
def Cached_Glob(pattern):
    from glob import glob
    return glob(pattern)

@cachetools.func.ttl_cache(maxsize=1, ttl=10*60)
def GetForwardUrl(url: str) -> str:
    return Config('voted_url', '?')
    # print(url)
    # if 'metin2pserver.net/' not in url:
    #     return Config('voted_url', '?')
    # elif 'vote' in url:
    #     return Config('voted_url', '?')
    # else:
    #     return url
    
def stacktrace() -> str:
    import traceback, sys
    exc = sys.exc_info()[0]
    stack = traceback.extract_stack()[:-1]  # last one would be full_stack()
    if exc is not None:  # i.e. an exception is present
        del stack[-1]       # remove call of full_stack, the printed exception
                            # will contain the caught exception caller instead
    trc = 'Traceback (most recent call last):\n'
    stackstr = trc + ''.join(traceback.format_list(stack))
    if exc is not None:
         stackstr += '  ' + traceback.format_exc().lstrip(trc)
    return stackstr

def get_linenumber() -> int:
    from inspect import currentframe
    cf = currentframe()
    return cf.f_back.f_lineno

@cachetools.func.ttl_cache(maxsize=50, ttl=20*60)
def GetCachedPILImage(path: str, convert: str) -> Image:
    im = Image.open(path)
    im = im.convert(convert)
    return im
    
def CropCircle(img: Image, resize: tuple = None) -> Image:
    if resize:
        img = img.resize(resize)        
    npImage=np.array(img)
    h,w=img.size
    alpha = Image.new('L', img.size,0)
    draw = ImageDraw.Draw(alpha)
    draw.pieslice([0,0,h,w],0,360,fill=255)
    npAlpha = np.array(alpha)
    npImage = np.dstack((npImage,npAlpha))
    img = Image.fromarray(npImage)
    return img

ICON_DATASET = None
def PrepareDataset():
    import os
    if not (os.path.isdir('res/cifar-10-batches-py') or os.path.isfile('res/cifar-10-python.tar.gz')):
        os.system('wget -c https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz -O res/cifar-10-python.tar.gz')
    
    if not os.path.isdir('res/cifar-10-batches-py'):
        print('no dir found so extracting tar.gz \n')
        os.system('cd res/ && tar xvzf cifar-10-python.tar.gz && cd ../')
    
    global ICON_DATASET
    with open('res/cifar-10-batches-py/data_batch_3', 'rb') as fo:
        import pickle
        data = pickle.load(fo, encoding='bytes')
        ICON_DATASET = data[b'data']
   
    if not (os.path.isdir('res/bgs') and os.path.isdir('res/bgs/test_lmdb') and os.path.isfile('res/bgs/test_lmdb.zip')):
        if not os.path.isdir('res/bgs/'):
            os.mkdir('res/bgs/')
        if not os.path.isdir('res/bgs/test_lmdb/'):
            os.mkdir('res/bgs/test_lmdb/')
        if not os.path.isfile('res/bgs/test_lmdb.zip'):
            os.system('wget -c http://dl.yf.io/lsun/scenes/test_lmdb.zip -O res/bgs/test_lmdb.zip')
    
    if not os.path.isdir('res/bgs/0'):
        print('no dir found so extracting zip \n')
        os.system('cd res/bgs && unzip -o test_lmdb.zip && cd ../../')
        
        db_path = 'res/bgs/test_lmdb/'
        out_dir = 'res/bgs/'
        flat=False
        limit=-1
                
        import lmdb        
        print('Exporting', db_path, 'to', out_dir)
        env = lmdb.open(db_path, map_size=1099511627776,
                        max_readers=100, readonly=True)
        count = 0
        with env.begin(write=False) as txn:
            cursor = txn.cursor()
            for key, val in cursor:
                if not flat:
                    image_out_dir = os.path.join(out_dir, '/'.join(key.decode('ascii')[:6]))
                else:
                    image_out_dir = out_dir
                if not os.path.exists(image_out_dir):
                    os.makedirs(image_out_dir)
                image_out_path = os.path.join(image_out_dir, key.decode('ascii') + '.webp')
                with open(image_out_path, 'wb') as fp:
                    fp.write(val)
                count += 1
                if count == limit:
                    break
                if count % 1000 == 0:
                    print('Finished', count, 'images')
                    
def SaveToTempFile(filename: str, obj: any) -> None:
    with open(filename, 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)
        
def LoadFromTempFile(filename: str, obj: any) -> None:
    if os.path.isfile(filename):
        with open(filename, 'rb') as f:
            obj = pickle.load(f)
        os.remove(filename)
    return obj
    