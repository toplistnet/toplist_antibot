from utils import Config
import mariadb
import cachetools
from random import randint
from copy import copy
import json

captcha_cache = cachetools.TTLCache(maxsize=256, ttl=3*60)

def GetNewCaptchaID() -> int:
    return randint(0, 2100000000)

def SetCaptchaData(id: int, data: str, expire: int = 60*5) -> None:
    captcha_cache[id] = data

def GetCaptchaData(id: int, is_test: bool) -> str:
    try:
        data = captcha_cache[id]
    except KeyError:
        return None
        
    if data:
        if not is_test:
            tmp = copy(captcha_cache[id])
            del captcha_cache[id]
            return tmp
        return data
    
    return None

def SaveCaptchaDataToFile() -> None:
    tmp = {}
    for k,v in captcha_cache.items():
        tmp[int(k)] = v
    open('.cache', 'w').write(json.dumps(tmp))
    
def LoadCaptchaDataFromFile() -> None:
    global captcha_cache
    from os.path import isfile
    if isfile('.cache'):
        with open('.cache', 'r') as r:
            if not len(r.read()):
                return
        
        tmp = json.load(open('.cache', 'r'))
        for k,v in tmp.items():
            captcha_cache[int(k)] = v
            
        from os import remove
        remove('.cache')

mysql = mariadb.connect(**{
    'user' : Config('db_user'),
    'password' : Config('db_pass'),
    'host' : Config('db_host'),
    'database' : Config('db_db'),
    'port' : Config('db_port'),
})

mysql.auto_reconnect = True
mysql.autocommit = True

def DBInsert(query: str, parameters: tuple) -> None:
    cursor = mysql.cursor()
    cursor.execute(query, parameters)
    mysql.commit()
    
def DBQueryOneField(query: str, parameters: tuple):
    cursor = mysql.cursor()
    cursor.execute(query, parameters)
    return cursor.fetchone()    
