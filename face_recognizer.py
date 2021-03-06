from __future__ import print_function
import dlib
from skimage import io
from scipy.spatial import distance
import matplotlib.pyplot as plt
import json
import pymongo
from os import listdir
from config import config
import numpy as np
from PIL import Image
# import face_recognition_models # if using load_model_from_dlib

# %matplotlib inline


class FaceRecognizer:

    def __init__(self):

        self.threshold = config.threshold
        self.model_file_name = config.model_file_name
        self.points_file_name = config.points_file_name
        self.likelihood = config.likelihood

    def load_image(self, name, show=True, title='Unknown'):

        pic = Image.open(name)
        pic.thumbnail(config.resize_value)
        image = np.array(pic)
        if not show:
            return image
        plt.figure()
        plt.imshow(image)
        plt.title(title)
        plt.show()
        return image

    def load_image1(self, name, show=True, title='Unknown'):

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

    # def load_model_from_dlib(self):
    #     self.detector = dlib.get_frontal_face_detector()
    #     predictor_68_point_model = face_recognition_models.pose_predictor_model_location()

    #     self.predictor = dlib.shape_predictor(predictor_68_point_model)
    #     face_recognition_model = face_recognition_models.face_recognition_model_location()

    #     self.model = dlib.face_recognition_model_v1(face_recognition_model)

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
        for face1 in descriptors1:
            for face2 in descriptors2:
                self.likelihood = min(self.likelihood, self.is_similar(face1, face2))
                if verbose:
                    print('Pair {}: difference {}'.format(count, self.likelihood))
                    print('')
                count += 1
        return

    def run(self):
        self.load_model(self.model_file_name, self.points_file_name)


class FaceComparator:
    '''
    Class to compare people from photos with some known people.
    '''

    def __init__(self):

        # self.image_file = image_file
        self.image_folder = config.image_folder
        self.dictionary_file = config.dictionary_file
        self.facer = FaceRecognizer()
        self.most_likely = config.comparator.get('most_likely')
        self.most_likeleys = config.comparator.get('most_likeleys')
        self.db = pymongo.MongoClient(
            config.mongo_config.get('host'),
            config.mongo_config.get('port')
            ).faces
        self.facer.run()

    def update_descriptors(self, all_descriptors, new_descriptors):
        result = list(all_descriptors)
        for new_d in new_descriptors:
            TO_ADD = True
            for old_d in all_descriptors:
                print('difference: ', self.facer.is_similar(old_d, new_d))
                if self.facer.is_similar(old_d, new_d) < config.distinct_descriptors_threshold:
                    TO_ADD = False
            if TO_ADD:
                result.append(new_d)
            print('total: ', len(result))
        return result

    def process_image_without_rotation(self, show=True):
        '''Load photo, find faces on it and describe them as vectors.
           The show parameter allows verbosity'''
        import timeit
        start = timeit.default_timer()
        self.image = self.facer.load_image(self.image_file, show)
        print('Loading image: ', timeit.default_timer()-start)
        self.faces = self.facer.detect_faces(self.image)
        print('Detecting faces: ', timeit.default_timer()-start)
        self.shapes = self.facer.make_mask(self.image, self.faces, show_coords=show)
        print('Making mask: ', timeit.default_timer()-start)
        self.descriptors = self.facer.get_face_descriptors(self.image, self.shapes)
        print('Time of processing: ', timeit.default_timer()-start)

    def process_image(self, show=True):
        '''Load photo, find faces on it and describe them as vectors.
           The show parameter allows verbosity'''

        self.image = self.facer.load_image(self.image_file, show)
        image = self.image
        faces = self.facer.detect_faces(image)
        shapes = self.facer.make_mask(image, faces, show_coords=show)
        self.descriptors = self.facer.get_face_descriptors(image, shapes)
        print('Currently faces: ', len(self.descriptors))
        for _ in range(3):
            image = np.rot90(image, k=1, axes=(0, 1))
            faces = self.facer.detect_faces(image)
            shapes = self.facer.make_mask(image, faces, show_coords=show)
            descriptors = self.facer.get_face_descriptors(image, shapes)
            print('++', len(descriptors))
            self.descriptors = self.update_descriptors(self.descriptors, descriptors)
            print(len(self.descriptors))

    def restore_default(self):
        '''Set all image parameters to None'''

        self.image_file = config.comparator.get('image_file')
        self.image = config.comparator.get('image')
        self.faces = config.comparator.get('faces')
        self.shapes = config.comparator.get('shapes')
        self.descriptors = config.comparator.get('descriptors')
        self.most_likely = config.comparator.get('most_likely')
        self.most_likeleys = config.comparator.get('most_likeleys')

    def load_dictionary(self):
        '''Load dictionary of numbers of known people and their actual names'''

        with open(self.dictionary_file) as f:
            self.dictionary = json.load(f)

    def compare_differences(self, difference, name):
        '''Upgrade the variable that contains most likely person'''

        if difference < self.most_likely[0]:
            self.most_likely = (difference, name)

    def compare_multiple_differences(self, difference, name, most_likely):
        if difference < most_likely[0]:
            return difference, name
        return most_likely

    def take_an_average(self, lists):
        n = float(len(lists))
        result = [0 for _ in range(len(lists[0]))]
        for i in range(len(lists[0])):
            for lst in lists:
                result[i] += lst[i][0]
        return [round(i/n, 3) for i in result]

    def iterate(self, show=False):
        '''Iterate on a dictionary to find a person most likely to be on the photo.
           The show parameter allows verbosity'''

        for key, name in self.dictionary.items():
            self.facer.__init__()
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
                self.facer.__init__()
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
                self.facer.__init__()
                descriptors = [face['descriptor']]
                self.facer.compare_faces(self.descriptors, descriptors, verbose=show)
                self.compare_differences(self.facer.likelihood, name)
                # print(self.most_likely)

    def multiple_iterate_over_db(self, show=False):

        self.most_likeleys = [config.comparator.get('most_likely') for i in range(len(self.descriptors))]
        for item in self.db.faces.find():
            name = item['name']
            for face in item['faces']:
                for idx in range(len(self.descriptors)):
                    photo_descriptor = [self.descriptors[idx]]
                    self.facer.__init__()
                    descriptors = [face['descriptor']]
                    self.facer.compare_faces(photo_descriptor, descriptors, verbose=show)
                    self.most_likeleys[idx] = self.compare_multiple_differences(
                        self.facer.likelihood,
                        name,
                        self.most_likeleys[idx])
        print(self.most_likeleys)

    def average_iterate_over_db(self, show=False):

        self.most_likeleys = [config.comparator.get('most_likely') for i in range(len(self.descriptors))]
        for item in self.db.faces.find():
            name = item['name']
            guesses = []
            for face in item['faces']:
                guess = [config.comparator.get('most_likely') for i in range(len(self.descriptors))]
                for idx in range(len(self.descriptors)):
                    photo_descriptor = [self.descriptors[idx]]
                    self.facer.__init__()
                    descriptors = [face['descriptor']]
                    self.facer.compare_faces(photo_descriptor, descriptors, verbose=show)
                    guess[idx] = (self.facer.likelihood, name)
                    for i in range(len(guess)):
                        if guess[i] == (0.0, name):
                            self.most_likeleys[i] = guess[i]
                guesses.append(guess)

            result_guess = self.take_an_average(guesses)
            # print(guesses)
            print('Name: ', name, ', Result guess: ', result_guess)

            for index in range(len(self.descriptors)):
                self.most_likeleys[index] = self.compare_multiple_differences(
                        result_guess[index],
                        name,
                        self.most_likeleys[index])
        print(self.most_likeleys)

    def display_name(self):
        '''Display answer in human-readable format'''

        print('\n----------------')
        FOUND = False
        if not self.most_likeleys:
            print('I do not see any faces on this photo!')
        else:
            print('I guess this is photo of: ')
            for face in self.most_likeleys:
                if face[0] < self.facer.threshold:
                    FOUND = True
                    print(face[1])
            if not FOUND:
                if len(self.most_likeleys) > 1:
                    print('{} unknown people'.format(len(self.most_likeleys)))
                else:
                    print('one unknown person')
        print('----------------')

    def main(self, image_file, show=True, iterator='avg_db'):
        '''Launcher. The show parameter allows verbosity'''

        # self.load_dictionary()
        self.image_file = image_file
        self.process_image(show=False)
        if iterator == 'db':
            self.iterate_over_db(show=False)
        elif iterator == 'multi_db':
            self.multiple_iterate_over_db(show=False)
        elif iterator == 'avg_db':
            self.average_iterate_over_db(show=False)
        elif iterator == 'folder':
            self.iterate_by_folders(show=False)
        if show:
            self.display_name()
        return self.most_likely


if __name__ == '__main__':
    facecom = FaceComparator()
    facecom.main('img/urgant2.jpg')
    # facecom.facer.load_image('img/urgant2.jpg')
