from singleton import Singleton
from strenum import StrEnum
from flask import jsonify, Blueprint
from utils import Config, SaveToTempFile, LoadFromTempFile

class Stats(Singleton):
    class what(StrEnum):
        captchas ='captchas'
        validations ='validations'
        invalid ='invalid'
        invalid_tests ='invalid_tests'
        valid ='valid'
        valid_tests ='valid_tests'
                
    all_stats: dict = {}
    
    def __init__(self) -> None:
        self.Reset('general')
        self.all_stats = LoadFromTempFile('.cache.stats', self.all_stats)
        
    def __del__(self) -> None:
        SaveToTempFile('.cache.stats', self.all_stats)
    
    def Reset(self, who: any) -> None:
        self.all_stats[who] = {
            'captchas' : 0,
            'validations' : 0,
            'invalid' : 0,
            'invalid_tests' : 0,
            'valid' : 0,
            'valid_tests' : 0,
        }
    
    def Add(self, server_id: int, what: what) -> None:
        self.all_stats['general'][what] = self.all_stats['general'][what] + 1
        
        if server_id not in self.all_stats:
            self.Reset(server_id)
        self.all_stats[server_id][what] = self.all_stats[server_id][what] + 1
        
    def Get(self, who: any, what: what = None) -> any:
        if who not in self.all_stats:
            self.Reset(who)
            
        if what:
            return self.all_stats[who][what]
        
        return self.all_stats[who]

    def Flush(self):
        self.all_stats.clear()
        self.__init__()

stats_blueprint = Blueprint('urls_stats', __name__)

@stats_blueprint.route('/admin/stats/get')
def web_stats_get_general():
    return jsonify(Stats().Get('general'))

@stats_blueprint.route('/admin/stats/get/<server_id>')
def web_stats_get_server(server_id: int):
    return jsonify(Stats().Get(server_id))

@stats_blueprint.route('/admin/stats/flush')
def web_stats_flush():
    Stats().Flush()
    return 'Stats Flushed'

class IPStats(Singleton):
    class what(StrEnum):
        captchas ='captchas'
        invalid ='invalid'
        valid ='valid'
                
    all_stats: dict = {}
    
    def __init__(self) -> None:
        self.all_stats = LoadFromTempFile('.cache.ipstats', self.all_stats)
        
    def __del__(self) -> None:
        SaveToTempFile('.cache.ipstats', self.all_stats)
        
    def Reset(self, ip: any) -> None:
        self.all_stats[ip] = {
            'captchas' : 0,
            'invalid' : 0,
            'valid' : 0,
        }
    
    def Add(self, ip: int, what: what) -> None:
        if ip not in self.all_stats:
            self.Reset(ip)
        self.all_stats[ip][what] = self.all_stats[ip][what] + 1
        
    def Get(self, ip: any = None, what: what = None) -> any:
        if not ip:
            return self.all_stats
        
        if ip not in self.all_stats:
            self.Reset(ip)
            
        if what:
            return self.all_stats[ip][what]
        
        return self.all_stats[ip]
    
    def Flush(self):
        self.all_stats.clear()

@stats_blueprint.route('/admin/stats/ip')
def web_voter_stats():
    return jsonify(IPStats().Get())

@stats_blueprint.route('/admin/stats/ip/flush')
def web_voter_stats_flush():
    IPStats().Flush()
    return 'Stats Flushed'

@stats_blueprint.route('/admin/stats/ip/<ip>')
def web_voter_stats_by_ip(ip):
    return jsonify(IPStats().Get(ip))

if __name__ == '__main__':
    Stats().Add(1, Stats().what.captchas)
    Stats().Add(1, Stats().what.captchas)
    print(str(Stats().Get(1)))