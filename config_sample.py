class Config():

    def __init__(self):

        self.mysql_config = {
            'host': 'host',
            'user': 'user',
            'password': 'password',
            'database': 'database',
            'cursorclass': 'cursorclass'
        }

        self.mongo_config = {
            'host': 'host',
            'port': 'port'
        }


config = Config()
