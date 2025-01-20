from app.app import db
from app.tools.utils import Config
from cachetools import TTLCache, cached

class Localization():
    LANGUAGES: list = []
    LOCALE_STRINGS: dict[str, dict[str, str]] = {}
    saveQueue: set = set()
    
    def __init__(self) -> None:
        self.LANGUAGES: list = str(object=Config(key='locales')).split(sep=',')

        for lang in self.LANGUAGES:
            self.LOCALE_STRINGS[lang] = {}
        
    async def Load(self) -> None:
        languages: str = ",lang_".join(self.LANGUAGES)
        languages = "lang_" + languages
        
        localization: dict = await db.queryDictByKey(query=
            f"SELECT {languages} FROM locale WHERE lang_en != '' AND uri = 'antibot.py'", 
            args={}, 
            ifnull='lang_en')
        # if int(Config("debug"))==1: print(f"LOCALIZATION: load [{localization}]")
        for k, v in localization.items():
            for lang in self.LANGUAGES:
                if lang not in self.LOCALE_STRINGS:
                    self.LOCALE_STRINGS[lang] = {}
                self.LOCALE_STRINGS["en"][k] = k
                for lang_key, lang_value in v.items():
                    if not lang_value:
                        lang_value = k
                    self.LOCALE_STRINGS[lang_key.replace("lang_", "")][k] = lang_value

        # if int(Config("debug"))==1: print(f"LOCALIZATION: LOADED {self.LOCALE_STRINGS}")
        self.loaded = True
        
    async def Save(self) -> None:
        for text in self.saveQueue.copy():
            if int(Config("debug"))==1: print(f"LOCALIZATION: save[{text}]")
            await db.insert(table="locale", data={
                    "lang_en" : text,
                    "uri" : "antibot.py",
                }, ignore_into=True)
        self.saveQueue.clear()

    @cached(cache=TTLCache(maxsize=1024*100, ttl=60))
    def Translate(self, language: str, string: str) -> str:
        if not self.loaded:
            if int(Config("debug"))==1: print("LOCALIZATION: lang not loaded")
            return string
        
        if string not in self.LOCALE_STRINGS[language]:
            self.saveQueue.add(string)
            if int(Config("debug"))==1: print(f"LOCALIZATION: not in strings [{string}]")
            for lang in self.LANGUAGES:
                self.LOCALE_STRINGS[lang][string] = string
        
        return self.LOCALE_STRINGS[language][string]
    