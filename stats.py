from typing import Literal
from flask.wrappers import Response
from singleton import Singleton
from strenum import StrEnum
from flask import jsonify, Blueprint
from utils import SaveToTempFile, LoadFromTempFile

class Stats(Singleton):
    class what(StrEnum):
        captchas ='captchas'
        validations ='validations'
        invalid ='invalid'
        invalid_tests ='invalid_tests'
        valid ='valid'
        valid_tests ='valid_tests'
        none = 'none'
                
    all_stats: dict = {}
    
    def __init__(self) -> None:
        self.Reset(who='general')
        self.all_stats = LoadFromTempFile(filename='.cache.stats')
        
    def __del__(self) -> None:
        SaveToTempFile(filename='.cache.stats', obj=self.all_stats)
    
    def Reset(self, who: str) -> None:
        self.all_stats[who] = {
            'captchas' : 0,
            'validations' : 0,
            'invalid' : 0,
            'invalid_tests' : 0,
            'valid' : 0,
            'valid_tests' : 0,
        }
    
    def Add(self, server_id: str, what: what) -> None:
        self.all_stats['general'][what] = self.all_stats['general'][what] + 1
        
        if server_id not in self.all_stats:
            self.Reset(who=server_id)
        self.all_stats[server_id][what] = self.all_stats[server_id][what] + 1
        
    def Get(self, who: str, what: str = ""):
        if who not in self.all_stats:
            self.Reset(who=who)
            
        if what:
            return self.all_stats[who][what]
        
        return self.all_stats[who]

    def Flush(self) -> None:
        self.all_stats.clear()
        self.__init__()

stats_blueprint = Blueprint(name='urls_stats', import_name=__name__)

@stats_blueprint.route(rule='/admin/stats/get')
def web_stats_get_general() -> Response:
    return jsonify(Stats().Get(who='general'))

@stats_blueprint.route(rule='/admin/stats/get/<server_id>')
def web_stats_get_server(server_id: int) -> Response:
    return jsonify(Stats().Get(who=str(object=server_id)))

@stats_blueprint.route(rule='/admin/stats/flush')
def web_stats_flush() -> Literal['Stats Flushed']:
    Stats().Flush()
    return 'Stats Flushed'

class IPStats(Singleton):
    class what(StrEnum):
        captchas ='captchas'
        invalid ='invalid'
        valid ='valid'
                
    all_stats: dict = {}
    
    def __init__(self) -> None:
        self.all_stats = LoadFromTempFile(filename='.cache.ipstats')
        
    def __del__(self) -> None:
        SaveToTempFile(filename='.cache.ipstats', obj=self.all_stats)
        
    def Reset(self, ip: str) -> None:
        self.all_stats[ip] = {
            'captchas' : 0,
            'invalid' : 0,
            'valid' : 0,
        }
    
    def Add(self, ip: str, what: what) -> None:
        if ip not in self.all_stats:
            self.Reset(ip)
        self.all_stats[ip][what] = self.all_stats[ip][what] + 1
        
    def Get(self, ip: str = "", what: what|None = None):
        if not ip:
            return self.all_stats
        
        if ip not in self.all_stats:
            self.Reset(ip=ip)
            
        if what:
            return self.all_stats[ip][what]
        
        return self.all_stats[ip]
    
    def Flush(self) -> None:
        self.all_stats.clear()

@stats_blueprint.route(rule='/admin/stats/ip')
def web_voter_stats() -> Response:
    return jsonify(IPStats().Get())

@stats_blueprint.route(rule='/admin/stats/ip/flush')
def web_voter_stats_flush() -> Literal['Stats Flushed']:
    IPStats().Flush()
    return 'Stats Flushed'

@stats_blueprint.route(rule='/admin/stats/ip/<ip>')
def web_voter_stats_by_ip(ip) -> Response:
    return jsonify(IPStats().Get(ip=ip))

if __name__ == '__main__':
    Stats().Add(server_id="1", what=Stats().what.captchas)
    Stats().Add(server_id="1", what=Stats().what.captchas)
    print(str(object=Stats().Get(who="1")))