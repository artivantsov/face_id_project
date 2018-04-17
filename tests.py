import unittest
import face_recognizer
from skimage import io
import dlib

facer = face_recognizer.FaceRecognizer()
img_name = 'test/img/test_urgant.jpg'
img_name1 = 'test/img/urgant2.jpg'
img_name2 = 'test/img/mart1.jpg'


class RecognizerTest(unittest.TestCase):

    def test_points_file(self):
        try:
            predictor = dlib.shape_predictor(facer.points_file_name)
        except RuntimeError:
            predictor = []
        self.assertNotEqual(predictor, [])

    def test_model_file(self):
        try:
            model = dlib.face_recognition_model_v1(facer.model_file_name)
        except RuntimeError:
            model = []
        self.assertNotEqual(model, [])

    def test_load_model(self):
        failed = False
        try:
            facer.load_model(facer.model_file_name, facer.points_file_name)
        except Exception:
            failed = True
        self.assertFalse(failed)

    def test_load_image(self):
        failed = False
        try:
            self.image = facer.load_image(img_name, title=img_name, show=False)
        except Exception:
            failed = True
        self.assertFalse(failed)

    def test_detect_face(self):
        image = facer.load_image(img_name, title=img_name, show=False)
        facer.load_model(facer.model_file_name, facer.points_file_name)
        faces = facer.detect_faces(image)
        self.assertGreater(len(faces), 0)

    def test_make_mask(self):
        image = facer.load_image(img_name, title=img_name, show=False)
        facer.load_model(facer.model_file_name, facer.points_file_name)
        faces = facer.detect_faces(image)
        shapes = facer.make_mask(image, faces, show_coords=False)
        self.assertGreater(len(shapes), 0)

    def test_get_face_descriptors(self):
        image = facer.load_image(img_name, title=img_name, show=False)
        facer.load_model(facer.model_file_name, facer.points_file_name)
        faces = facer.detect_faces(image)
        shapes = facer.make_mask(image, faces, show_coords=False)
        descriptors = facer.get_face_descriptors(image, shapes)
        self.assertGreater(len(descriptors), 0)

    def test_compare_faces1(self):
        facer.load_model(facer.model_file_name, facer.points_file_name)
        image1 = facer.load_image(img_name, title=img_name, show=False)
        image2 = facer.load_image(img_name1, title=img_name1, show=False)
        faces1 = facer.detect_faces(image1)
        faces2 = facer.detect_faces(image2)
        shapes1 = facer.make_mask(image1, faces1, show_coords=False)
        shapes2 = facer.make_mask(image2, faces2, show_coords=False)
        descriptors1 = facer.get_face_descriptors(image1, shapes1)
        descriptors2 = facer.get_face_descriptors(image2, shapes2)
        fits = facer.compare_faces(descriptors1, descriptors2, verbose=False)
        self.assertGreater(fits, 0)

    def test_compare_faces2(self):
        facer.load_model(facer.model_file_name, facer.points_file_name)
        image1 = facer.load_image(img_name, title=img_name, show=False)
        image2 = facer.load_image(img_name2, title=img_name2, show=False)
        faces1 = facer.detect_faces(image1)
        faces2 = facer.detect_faces(image2)
        shapes1 = facer.make_mask(image1, faces1, show_coords=False)
        shapes2 = facer.make_mask(image2, faces2, show_coords=False)
        descriptors1 = facer.get_face_descriptors(image1, shapes1)
        descriptors2 = facer.get_face_descriptors(image2, shapes2)
        fits = facer.compare_faces(descriptors1, descriptors2, verbose=False)
        self.assertEqual(fits, 0)


img1_name = 'test/img/test_urgant.jpg'
img2_name = 'test/img/test_svet.jpg'
test_image_folder = 'test/img/ordered/'
image_folder = 'img/ordered/'
dictionary_file = 'test/img/ordered/dictionary.json'


class ComparatorTest(unittest.TestCase):

    def test_positive(self):
        facecom = face_recognizer.FaceComparator(img1_name)
        facecom.image_folder = image_folder
        facecom.dictionary_file = dictionary_file
        result = facecom.main(show=False, iterator=facecom.iterate_by_folders)[1]
        self.assertEqual(result, 'Ivan Urgant')

    def test_negative(self):
        facecom = face_recognizer.FaceComparator(img2_name)
        result = facecom.main(show=False, iterator=facecom.iterate_by_folders)[0]
        self.assertGreater(result, facecom.facer.threshold)

    def test_dictionary_file(self):
        try:
            facecom = face_recognizer.FaceComparator(img1_name)
            facecom.load_dictionary()
        except FileNotFoundError:
            facecom.dictionary = {}
        self.assertNotEqual(facecom.dictionary, {})

    def test_image_base(self):
        facecom = face_recognizer.FaceComparator(img1_name)
        facecom.load_dictionary()
        failed = False
        for key in facecom.dictionary.keys():
            try:
                io.imread(image_folder+key+'.jpg')
            except FileNotFoundError:
                print('Image number {} not found.'.format(key))
                failed = True
        self.assertFalse(failed)


calcTestSuite = unittest.TestSuite()
calcTestSuite.addTest(unittest.makeSuite(RecognizerTest))
calcTestSuite.addTest(unittest.makeSuite(ComparatorTest))

print("count of tests: " + str(calcTestSuite.countTestCases()) + "\n")

runner = unittest.TextTestRunner(verbosity=2)
testResult = runner.run(calcTestSuite)

print("errors")
print(len(testResult.errors))
print("failures")
print(len(testResult.failures))
print("skipped")
print(len(testResult.skipped))
print("testsRun")
print(testResult.testsRun)
