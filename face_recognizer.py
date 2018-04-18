import dlib
from skimage import io
from scipy.spatial import distance
import matplotlib.pyplot as plt
import json
import pymongo
from os import listdir
from config import config

# %matplotlib inline


class FaceRecognizer:

    def __init__(self):

        self.threshold = config.threshold
        self.model_file_name = config.model_file_name
        self.points_file_name = config.points_file_name
        self.likelihood = config.likelihood

    def load_image(self, name, show=True, title='Unknown'):

        image = io.imread(name)
        if not show:
            return image
        plt.figure()
        plt.imshow(image)
        plt.title(title)
        plt.show()
        return image

    def threshold_checker(self, value, show=True):

        if value <= self.threshold:
            if show:
                print('YAHOO!! SAME FACES!')
            return True
        else:
            if show:
                print("Stop! They're different!")
            return False

    def load_model(self, model_file, points_file):
        self.predictor = dlib.shape_predictor(points_file)
        self.model = dlib.face_recognition_model_v1(model_file)
        self.detector = dlib.get_frontal_face_detector()

    def detect_faces(self, image):
        return self.detector(image, 1)

    def make_mask(self, image, faces, show_coords=True):

        shapes = []
        if not faces:
            if show_coords:
                print('No faces found')
            return shapes

        for key, face in enumerate(faces):
            if show_coords:
                print("Detection {}: Left: {} Top: {} Right: {} Bottom: {}".format(
                 key+1, face.left(), face.top(), face.right(), face.bottom()))
            shape = self.predictor(image, face)
            shapes.append(shape)

        return shapes

    def get_face_descriptors(self, image, shapes):
        descriptors = []
        for shape in shapes:
            descriptors.append(self.model.compute_face_descriptor(image, shape))
        return descriptors

    def is_similar(self, descriptor1, descriptor2):
        return distance.euclidean(descriptor1, descriptor2)

    def compare_faces(self, descriptors1, descriptors2, verbose=True):
        count = 1
        fits = 0
        for face1 in descriptors1:
            for face2 in descriptors2:
                self.likelihood = self.is_similar(face1, face2)
                fits += int(self.threshold_checker(round(self.likelihood, 3), show=verbose))
                if verbose:
                    print('Pair {}: difference {}'.format(count, self.likelihood))
                    print('')
                count += 1
        return fits

    def run(self):
        self.load_model(self.model_file_name, self.points_file_name)


class FaceComparator:
    '''
    Class to compare people from photos with some known people.
    '''

    def __init__(self, image_file):

        self.image_file = image_file
        self.image_folder = config.image_folder
        self.dictionary_file = config.dictionary_file
        self.facer = FaceRecognizer()
        self.most_likely = config.initial_most_likely
        self.db = pymongo.MongoClient(
            config.mongo_config.get('host'),
            config.mongo_config.get('port')
            ).faces

    def process_image(self, show=True):
        '''Load photo, find faces on it and describe them as vectors.
           The show parameter allows verbosity'''

        self.facer.run()
        self.image = self.facer.load_image(self.image_file, show)
        self.faces = self.facer.detect_faces(self.image)
        self.shapes = self.facer.make_mask(self.image, self.faces, show_coords=show)
        self.descriptors = self.facer.get_face_descriptors(self.image, self.shapes)

    def load_dictionary(self):
        '''Load dictionary of numbers of known people and their actual names'''

        with open(self.dictionary_file) as f:
            self.dictionary = json.load(f)

    def compare_differences(self, difference, name):
        '''Upgrade the variable that contains most likely person'''

        if difference < self.most_likely[0]:
            self.most_likely = (difference, name)

    def iterate(self, show=False):
        '''Iterate on a dictionary to find a person most likely to be on the photo.
           The show parameter allows verbosity'''

        for key, name in self.dictionary.items():
            current_file = self.image_folder+key+'.jpg'
            image = self.facer.load_image(current_file, show=show, title=name)
            faces = self.facer.detect_faces(image)
            shapes = self.facer.make_mask(image, faces, show_coords=show)
            descriptors = self.facer.get_face_descriptors(image, shapes)
            self.facer.compare_faces(self.descriptors, descriptors, verbose=show)
            self.compare_differences(self.facer.likelihood, name)

    def iterate_by_folders(self, show=False):
        for key, name in self.dictionary.items():
            path = self.image_folder+key
            for file in listdir(path):
                image = self.facer.load_image(path+'/'+file, show=show, title=name)
                faces = self.facer.detect_faces(image)
                shapes = self.facer.make_mask(image, faces, show_coords=show)
                descriptors = self.facer.get_face_descriptors(image, shapes)
                self.facer.compare_faces(self.descriptors, descriptors, verbose=show)
                self.compare_differences(self.facer.likelihood, name)

    def iterate_over_db(self, show=False):
        for item in self.db.faces.find():
            name = item['name']
            for face in item['faces']:
                descriptors = [face['descriptor']]
                self.facer.compare_faces(self.descriptors, descriptors, verbose=show)
                self.compare_differences(self.facer.likelihood, name)

    def display_name(self):
        '''Display answer in human-readable format'''

        print('\n----------------')
        if self.most_likely[0] < self.facer.threshold:
            print('I guess this is photo of {}!'.format(self.most_likely[1]))
        elif self.most_likely[0] > 1:
            print('I do not see any faces on this photo!')
        else:
            print("Face on this photo doesn't look familiar for me!")
        print('----------------')

    def main(self, show=True, iterator='db'):
        '''Launcher. The show parameter allows verbosity'''

        self.load_dictionary()
        self.process_image(show=False)
        if iterator == 'db':
            self.iterate_over_db(show=False)
        elif iterator == 'folder':
            self.iterate_by_folders(show=False)
        if show:
            self.display_name()
        return self.most_likely


if __name__ == '__main__':
    facecom = FaceComparator('img/urgant2.jpg')
    facecom.main()
