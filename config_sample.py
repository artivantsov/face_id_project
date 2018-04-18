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
            'low_confidence': False
        }
        self.threshold = 0.55
        self.model_file_name = 'model.dat'
        self.points_file_name = 'points.dat'
        self.likelihood = 2
        self.image_folder = 'img/ordered/'
        self.dictionary_file = 'img/ordered/dictionary.json'
        self.initial_most_likely = (2, 'Unknown')


config = Config()
