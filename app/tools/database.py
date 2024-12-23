from muffin_databases import Plugin as DB
from muffin import Application
from sqlalchemy.engine.row import Row
from datetime import datetime
from aquiche import alru_cache
import json
from datetime import datetime

class Database():
    """
        This is a wrapper/extension module
    """

    db: DB

    def __init__(self, app: Application, connection_string: str) -> None:
        self.db = DB(url=connection_string)
        self.db.setup(app)

    @staticmethod
    def _extract_dict_from_row(data: Row, datetime_to_string: bool = False) -> dict:
        ret: dict = {}
        cols = list(data.keys())
        for i, col in enumerate(iterable=cols):
            if isinstance(data[i], datetime):
                ret[col] = data[i].strftime("%Y-%m-%d %H:%M:%S")
            else:
                ret[col] = data[i]
                
        return ret

    def generate_columns(self, data: dict) -> str:
        """
            dict -> keys as column names separated by ,
        """

        col_names: str = "`,`".join(data.keys())

        return "`" + col_names + "`"

    def generate_values(self, data: dict) -> str:
        """
            dict -> prepare values parameterized
        """

        values: str = ""
        for k, v in data.items():
            values += f":{k},"

        return values[:-1]

    async def query(self, query: str, args: dict = {}) -> list[dict] | int:
        """
            Executes a query and returns affectedRows/insertID/Select result
        """

        if not query:
            return 0

        if ' log.log ' in query:
            day: str = datetime.now().strftime('%d_%m_%Y')
            query = query.replace(' log.log ', f' log.log_{day} ')

        try:
            if query.strip().upper().startswith('SELECT'):
                result = await self.db.fetch_all(query, values=args)
                return list(dict(row) for row in result)
    
            result = await self.db.execute(query, values=args)
            # if self.cfg.app.debug and not result:
            #     print(query + "|" + str(object=args))

            return result
        except Exception as e:
            print(query + "|" + str(object=args))
            print(str(object=e))
            
        return 0
    
    async def update(self, query: str, args: dict) -> int:
        return await self.query(query=query, args=args)

    async def queryCached(self, query: str, args: dict = {}) -> list[dict]:
        return await self.__queryCached(query=query, args=json.dumps(obj=args))
    
    @alru_cache(expiration=300)
    async def __queryCached(self, query: str, args: str) -> list[dict]:
        return await self.query(query=query, args=json.loads(s=args))

    async def queryField(self, query: str, args: dict = {}) -> any: # type: ignore
        """
            Returns first field
        """

        # if self.cfg.app.debug:
        #     print(query + "|" + str(object=args))

        return await self.db.fetch_val(query, values=args)

    async def queryRow(self, query: str, args: dict = {}) -> any: # type: ignore
        """
            Returns first row
        """

        # if self.cfg.app.debug:
        #     print(query + "|" + str(object=args))

        return await self.db.fetch_one(query, values=args)

    async def queryRowDict(self, query: str, args: dict = {}) -> dict:
        """
            Returns a dict of the first entry {id:123,name:'xyz',..}
        """

        row = await self.db.fetch_one(query, values=args)
        if row:
            return self._extract_dict_from_row(data=row, datetime_to_string=True)

        return {}
    
    async def queryRowDictCached(self, query: str, args: dict = {}) -> dict:
        return await self.__queryRowDictCached(query=query, args=json.dumps(obj=args))
    
    @alru_cache(expiration=300)
    async def __queryRowDictCached(self, query: str, args: str) -> dict:
        return await self.queryRowDict(query=query, args=json.loads(s=args))
    

    async def queryFieldArray(self, query: str, args: dict = {}) -> list:
        """
            Returns an array of every first fields
        """

        ret: list = []
        result: list[dict] = await self.query(query=query, args=args)
        if result and len(result):
            for r in result:
                a = list(r.values())[0]
                ret.append(int(a) if str(object=a).isdigit() else a)

        return ret
    
    async def queryFieldArrayCached(self, query: str, args: dict = {}) -> list:
        return await self.__queryFieldArrayCached(query=query, args=json.dumps(obj=args))
    
    @alru_cache(expiration=300)
    async def __queryFieldArrayCached(self, query: str, args: str) -> list:
        return await self.queryFieldArray(query=query, args=json.loads(s=args))

    async def queryPairDict(self, query: str, args: dict = {}) -> dict:
        """
            Returns a dict of first 2 fields
        """

        ret: dict = {}
        result: list[dict] = await self.query(query=query, args=args)
        if not result:
            return ret
        
        if len(result) == 1:
            if list(result[0].values())[0] == None:
                return {}

        for r in result:
            a = list(r.values())
            ret[a[0]] = a[1]

        return ret
    
    async def queryPairDictCached(self, query: str, args: dict = {}) -> dict:
        return await self.__queryPairDictCached(query=query, args=json.dumps(obj=args))
    
    @alru_cache(expiration=300)
    async def __queryPairDictCached(self, query: str, args: str) -> dict:
        return await self.queryPairDict(query=query, args=json.loads(s=args))

    async def queryDictByKey(self, query: str, args: dict = {}, ifnull=None) -> dict:
        """
            Returns a dict of each line with key(first col) {key:{col:val,..}}
        """

        ret: dict = {}
        results: list[dict] = await self.query(query=query, args=args)
        if not results:
            return ret
        
        if len(results) == 1:
            if list(results[0].values())[0] == None:
                return {}

        for r in results:
            cols = list(r.keys())
            vals = list(r.values())

            ret[vals[0]] = {}

            for col in cols[1:]:
                ret[vals[0]][col] = r[col]
                if ifnull and type(r[col]) is str and not len(r[col]):
                    ret[vals[0]][col] = r[ifnull]

        return ret
    
    async def queryDictByKeyCached(self, query: str, args: dict = {}, ifnull=None) -> dict:
        return await self.__queryDictByKeyCached(query=query, args=json.dumps(obj=args), ifnull=ifnull)
    
    @alru_cache(expiration=300)
    async def __queryDictByKeyCached(self, query: str, args: str, ifnull=None) -> dict:
        return await self.queryDictByKey(query=query, args=json.loads(s=args), ifnull=ifnull)

    async def insert(self, table: str, data: dict, ignore_into: bool = True) -> int:
        """
            Automatically builds a proper insert query
        """

        col_names: str = self.generate_columns(data=data)
        values_str: str = self.generate_values(data=data)

        ignore: str = 'IGNORE ' if ignore_into else ''
        query: str = f"INSERT {ignore}INTO {table} ({col_names}) VALUES ({values_str})"

        result: list[dict] = await self.query(query=query, args=data)
        
        try:
            result = int(str(result))
            return result
        except:
            pass

        return 0

    async def copy_table(self, table, new_name, copy_data=True) -> None:
        """
            Duplicates a table
        """

        await self.query(query=f"CREATE TABLE {new_name} LIKE {table};", args={})
        if copy_data:
            await self.query(query=f"INSERT INTO {new_name} SELECT * FROM {table};", args={})
