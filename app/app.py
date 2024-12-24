import sys
sys.dont_write_bytecode = True
from muffin import Application
# TODO: add sentry
from app.tools.utils import Config

app = Application(name="toplist_antibot", debug=True, static_url_prefix='/assets', static_folders=["res"])

import redis.asyncio as redispy
redis_pool: redispy.BlockingConnectionPool = redispy.BlockingConnectionPool.from_url(url="redis://127.0.0.1:6379/4", 
                                                                                     decode_responses=True, 
                                                                                     timeout=3, 
                                                                                     max_connections=300)
redis = redispy.StrictRedis(connection_pool=redis_pool)

from app.tools.database import Database
user: str = str(object=Config(key='db_user'))
password: str = str(object=Config(key='db_pass'))
host: str = str(object=Config(key='db_host'))
port: str = str(object=Config(key='db_port'))
database: str = str(object=Config(key='db_db'))
db = Database(app=app, connection_string=f"mysql://{user}:{password}@{host}:{port}/{database}")

from app.tools.localization import Localization
localization = Localization()
app.on_startup(fn=localization.Load)

import muffin_jinja2
jinja2 = muffin_jinja2.Plugin()
jinja2.setup(app=app, template_folders=["res"], auto_reload=True, cache_size=100)
jinja2.add_global(obj=localization.Translate)

from app.routes import *
from app.api import *
from app.middleware import *
