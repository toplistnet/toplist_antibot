from db import DBInsert, DBQueryOneField
from utils import Config
from flask import Blueprint
from singleton import Singleton

# TODO: replace mariadb with api calls to website
class Localization(Singleton):

    LANGUAGES = []
    LOCALE_STRINGS = {}
    
    def __init__(self) -> None:
        self.LANGUAGES: list = str(object=Config(key='locales')).split(sep=',')

        for lang in self.LANGUAGES:
            self.LOCALE_STRINGS[lang] = {}

    def Translate(self, language: str, string: str) -> str:
        if language not in self.LANGUAGES:
            print(f"Language Error '{language}' '{string}'")
            return string
        
        if string not in self.LOCALE_STRINGS[language]:
            q_locales = ""
            for lang in self.LANGUAGES:
                q_locales += "lang_" + lang + ","
            q_locales = q_locales[:-1]     
            
            cols = DBQueryOneField(query="SELECT %s FROM locale WHERE lang_en=?;" % q_locales, parameters=(string,))
            if not cols:
                DBInsert(query="INSERT INTO locale (lang_en, uri) VALUES (?, ?)", parameters=(string, 'antibot.py'))
                print("added new translation %s" % string)
                return string
            else:
                for lang in self.LANGUAGES:
                    self.LOCALE_STRINGS[lang][string] = cols[self.LANGUAGES.index(lang)]
                    if not cols[self.LANGUAGES.index(lang)]:
                        self.LOCALE_STRINGS[lang][string] = cols[self.LANGUAGES.index('en')]
                        
        return self.LOCALE_STRINGS['en'][string] if not self.LOCALE_STRINGS[language][string] else self.LOCALE_STRINGS[language][string]

locale_blueprint = Blueprint(name='urls_locale', import_name=__name__)
@locale_blueprint.route(rule='/admin/localization/flush')
def web_localization_flush():
    Localization().__init__()
    return 'Flushed Localization'

if __name__ == "__main__":    
    print(Localization().Translate(language='ro', string="ANTI BOT EN"))