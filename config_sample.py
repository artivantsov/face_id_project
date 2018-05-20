class Config():

    def __init__(self):

        self.mysql_config = {
            'host': 'your_host',
            'user': 'your_user',
            'password': 'your_password',
            'database': 'your_database',
            'cursorclass': 'your_cursorclass'
        }

        self.mongo_config = {
            'host': 'your_host',
            'port': 'your_port'
        }
        self.tracker = {
            'descriptor': [],
            'name': '',
            'true_name': '',
            'author': '',
            'confidence': 2.0,
            'assessment': {},
            'multiple_faces': False,
            'no_faces': False,
            'faces_number': 0,
            'low_confidence': False,
            'precise_prediction': False,
        }
        self.threshold = 0.55
        self.model_file_name = 'model.dat'
        self.points_file_name = 'points.dat'
        self.likelihood = 2
        self.image_folder = 'img/ordered/'
        self.dictionary_file = 'img/ordered/dictionary.json'
        self.initial_most_likely = (2, 'Unknown')
        self.secret_key = 'your_secret_key'
        self.telegram_token = 'your_telegram_bot_token'
        self.my_telegram_id = 1234567890
        self.request_kwargs = {
                'proxy_url': 'proxy_server_url',
                'urllib3_proxy_kwargs': {
                    'username': 'user',
                    'password': 'pass',
                }
            }
        self.telegram_timeout = 2


config = Config()
