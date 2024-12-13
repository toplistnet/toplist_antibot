import logging
logging.basicConfig(format='%(asctime)s  %(levelname)s  %(message)s', 
                    filename='log.log', encoding='utf-8', level=logging.DEBUG)

from utils import Config, PrepareDataset
from db import LoadCaptchaDataFromFile, SaveCaptchaDataToFile
from captcha1 import Thread_PreGenerateCaptchas1
from captcha2 import Thread_PreGenerateCaptchas2
from threading import Thread

if __name__ == '__main__':
    from sys import version_info, exit
    if not version_info >= (3,9):
        print("requres python 3.9")
        exit(1)
    
    PrepareDataset()
        
    LoadCaptchaDataFromFile()
    
    Thread(target=Thread_PreGenerateCaptchas1, daemon=True).start()
    Thread(target=Thread_PreGenerateCaptchas2, daemon=True).start()
    
    from app import app
    from cheroot.wsgi import Server, PathInfoDispatcher
    
    d = PathInfoDispatcher(apps={'/': app})
    server = Server(
        bind_addr=(Config(key='ip', default='127.0.0.1'), int(Config(key='port', default="8001"))), 
        wsgi_app=d, 
        numthreads=int(Config(key='threads', default="5")),
        server_name='x', 
        max=int(Config(key='threads_max', default="20")), 
        reuse_port=True)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nshutdown\n")
        server.stop()
    finally:
        SaveCaptchaDataToFile()
        
        from stats import Stats, IPStats
        Stats().__del__()
        IPStats().__del__()