import requests
import sys
import time
from threading import Thread
from random import randint

def TestRequest():
    while True:
        try:
            t1 = time.time()
            
            url = "http://127.0.0.1:8001/captcha"
            if len(sys.argv) > 3 and int(sys.argv[3]) > 0:
                url += "?profile"
                
            response = requests.post(url, data = {
                'voted' : 1,
                'server_id' : 1,
                'player_id' : '1',
                '_f' : '1',
                'locale' : 'en',
            })
            
            t2 = time.time()
            if len(sys.argv) > 3 and int(sys.argv[3]) > 0:
                print(response.text)      
                print(f"Captcha gen    #{t2-t1:.4f}   ")
                return
            
            captcha_id = response.text.split('<input type="hidden" name="id" value="')[1].split('"',1)[0]

            url = "http://127.0.0.1:8001/validate"
            if len(sys.argv) > 4 and int(sys.argv[4]) > 0:
                url += "?profile"
            
            t3 = time.time()
            response = requests.post(url, data = {
                'voted' : 1,
                'server_id' : 1,
                'player_id' : '1',
                '_f' : '1',
                'id' : int(captcha_id),
                # 'captcha' : 'clickicon',
                # 'clicks' : f'[{ randint(1, 299) }.1,{ randint(1, 299), {time.time()} }]',
                'captcha' : 'findone',
                'click' : f'[{ randint(1, 299) }.1,{ randint(1, 299) }.1]',
                'test' : 1,
            })
            
            t4 = time.time()
            print(response.text)
            print(f"Captcha[{captcha_id}    #{t2-t1:.4f}    #{t4-t3:.4f}")
        except Exception as e:
            print(f"EXCEPTION {e}")
        time.sleep(float(sys.argv[2]))
    
if __name__ == '__main__':    
    if len(sys.argv) < 3:
        print(f"{sys.argv[0]} <threads> <delay> <profile_captcha=0/1> <profile_valdiation=0/1>")
        sys.exit(-1)
    
    for x in range(int(sys.argv[1])):
        Thread(target=TestRequest, args=()).start()
        
else:
    print("Test Suite can't be imported")