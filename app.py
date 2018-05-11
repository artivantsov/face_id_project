from flask import Flask, render_template, flash, redirect, url_for, session
from flask import request
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
from wtforms import Form, StringField, PasswordField, validators
from flask_wtf.file import FileField, FileRequired, FileAllowed
from flask_wtf import FlaskForm
from passlib.hash import sha256_crypt
from functools import wraps
from werkzeug.utils import secure_filename
import os
from face_recognizer import FaceComparator
import json
import pymongo
from bson.objectid import ObjectId
from datetime import datetime
from config import config

app = Flask(__name__)

app.config['UPLOADED_PHOTOS_DEST'] = os.getcwd()
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)
patch_request_class(app)  # set maximum file size, default is 16MB
client = pymongo.MongoClient(
        host=config.mongo_config.get('host'),
        port=config.mysql_config.get('port')
        )
db = client.faces


class Tracker():
    '''Tracker of assessment results'''

    def __init__(self):
        self.descriptor = config.tracker.get('descriptor')
        self.name = config.tracker.get('name')
        self.true_name = config.tracker.get('true_name')
        self.author = config.tracker.get('author')
        self.confidence = config.tracker.get('confidence')
        self.assessment = config.tracker.get('assessment')
        self.multiple_faces = config.tracker.get('multiple_faces')
        self.no_faces = config.tracker.get('no_faces')
        self.faces_number = config.tracker.get('faces_number')
        self.low_confidence = config.tracker.get('low_confidence')
        self.precise_prediction = config.tracker.get('precise_prediction')


tracker = Tracker()


# Index
@app.route('/')
def index():
    return render_template('home.html')


# About
@app.route('/about')
def about():
    return render_template('about.html')


# Images
@app.route('/images')
def images():
    result = db.archive.find({'to_show': True}).sort('create_date', -1)

    if result.count() > 0:
        return render_template('images.html', images=result)
    else:
        msg = 'No images found'
        return render_template('images.html', msg=msg)


# Single image
@app.route('/images/<string:id>/')
def image(id):
    image = db.archive.find_one({'_id': ObjectId(id)})
    return render_template('image.html', image=image)


# Register Form class
class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')])
    confirm = PasswordField('Confirm Password')


# User register
@app.route('/register/', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        user = {'name': name, 'email': email, 'username': username, 'password': password}

        db.users.save(user)

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('login'))
    return render_template('register.html', form=form)


# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get Form Fields
        username = request.form['username']
        password_candidate = request.form['password']

        data = db.users.find_one({'username': username})

        if data:
            password = data['password']

            # Compare passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid password'
                return render_template('login.html', error=error)
        else:
            error = 'Username not found'
            return render_template('login.html', error=error)

    return render_template('login.html')


# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))
    return wrap


# Calculate confidence from difference
def confidence_calculator(difference):
    return round(100*(1-difference), 1)


# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))


# Image form
class ImagePostForm(FlaskForm):
    name = StringField('Name', [validators.Length(min=1, max=200)])
    true_name = StringField('True name', [validators.Length(min=1, max=200)])


def save_error_to_db():
    archive = {
        'name': tracker.name,
        'confidence': tracker.confidence,
        'author': session['username'],
        'create_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'true_name': tracker.true_name,
        'no_faces': tracker.no_faces,
        'multiple_faces': tracker.multiple_faces,
        'low_confidence': tracker.low_confidence,
        'precise_prediction': tracker.precise_prediction,
        'error': True,
        'to_show': True
        }
    db.archive.save(archive)


# Assessment
@app.route('/assessment/<string:assessment>')
def assessment(assessment):
    # form = ImagePostForm()
    error = False
    if assessment:
        assessment = json.loads(assessment)
        no_faces = assessment.get('no_faces')
        multiple_faces = assessment.get('multiple_faces')
        low_confidence = assessment.get('low_confidence')
        # resemblance = confidence_calculator(assessment.get('difference'))
        if no_faces:
            text = "I don't see any faces here... :("
            result_code = 0
            error = True
        elif multiple_faces:
            result_code = 2
            error = True
            if low_confidence:
                text = "I see {} faces here. But I actually don't know any of them!".format(tracker.faces_number)
            else:
                text = "I see {} faces here. One of them is definately {}!".format(tracker.faces_number, assessment.get('person'))
        elif low_confidence:
            error = True
            result_code = 3
            text = "This person doesn't look familiar..."
        else:
            result_code = 1
            text = 'It seems to me, this is a photo of {}'.format(assessment.get('person'))
        if error:
            print('Error')
            save_error_to_db()
        flash('Assessment page', 'success')
        return render_template('assessment.html', result_code=result_code, text=text)  # msg=msg,
    text = "There was some error. No assessment received."
    return render_template('assessment.html', result_code=-1, text=text)


# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():

    result = db.faces.find().sort('name', 1)

    if result.count() > 0:
        return render_template('dashboard.html', images=result)
    else:
        msg = 'No images found'
        return render_template('dashboard.html', msg=msg)


# Face recognition
def recognize(image):
    facecom = FaceComparator(image)
    facecom.main()
    return facecom.most_likely[0], facecom.most_likely[1], facecom.descriptors


# Image Form class
class ImageForm(FlaskForm):
    # title = StringField('Title', [validators.Length(min=1, max=200)])
    # body = TextAreaField('Text', [validators.Length(min=30)])
    # image = TextAreaField('Image', [validators.Length(min=1, max=50)])
    image = FileField(validators=[FileAllowed(photos, u'Image only!'), FileRequired(u'File is empty!')])
    # submit = SubmitField(u'Upload')


# Try new image
@app.route('/try_image', methods=['GET', 'POST'])
@is_logged_in
def try_image():
    try:
        tracker.__init__()
        form = ImageForm()
        if request.method == 'POST':
            if 'image' not in request.files:
                flash('No file found')
            else:
                file = request.files['image']
                filename = 'temp/'+secure_filename(file.filename)
                file.save(filename)

            try:
                assessment = {}
                assessment["difference"], assessment["person"], descriptor = recognize(file)
            except Exception as e:
                print(e)
                assessment = {"difference": 1, "person": "Not assessed"}
                descriptor = []
            if assessment.get('difference') == 0:
                tracker.precise_prediction = True
            resemblance = confidence_calculator(assessment.get('difference'))
            if resemblance < 100*(1-config.threshold):
                tracker.low_confidence = True
            if not descriptor:
                tracker.no_faces = True

            tracker.name = assessment.get('person')
            tracker.confidence = confidence_calculator(assessment.get('difference'))
            if not tracker.no_faces:
                try:
                    tracker.descriptor = list(descriptor[0])
                except Exception:
                    print('Could not get a response from recognize(). Assessment: {}'.format(str(assessment)))
            if len(descriptor) > 1:
                tracker.multiple_faces = True
            tracker.faces_number = len(descriptor)

            assessment['no_faces'] = tracker.no_faces
            assessment['multiple_faces'] = tracker.multiple_faces
            assessment['low_confidence'] = tracker.low_confidence
            assessment['precise_prediction'] = tracker.precise_prediction

            assessment = json.dumps(assessment)
            return redirect(url_for('assessment', assessment=assessment))

        return render_template('try_image.html', form=form)
    except Exception as e:
        print('Exception in correct_guess(): {}, {}'.format(str(e), str(e.args)))
        return render_template('try_image.html', form=form)


# If guess was correct
@app.route('/assessment/correct_guess', methods=['POST'])
@is_logged_in
def correct_guess():
    try:
        tracker.true_name = tracker.name

        archive = {
                'name': tracker.name,
                'confidence': tracker.confidence,
                'author': session['username'],
                'create_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'true_name': tracker.true_name,
                'no_faces': tracker.no_faces,
                'multiple_faces': tracker.multiple_faces,
                'low_confidence': tracker.low_confidence,
                'precise_prediction': tracker.precise_prediction,
                'error': False,
                'to_show': True,
                }
        archive_id = db.archive.save(archive)

        # Add to mongo
        new_face = {
            'author': session['username'],
            'guess': tracker.name,
            'confidence': tracker.confidence,
            'descriptor': tracker.descriptor,
            'archive_id': archive_id
            }

        if (not tracker.multiple_faces) and (not tracker.no_faces) and \
                (not tracker.low_confidence) and (not tracker.precise_prediction):
            mongo_item = db.faces.find_one({'name': tracker.true_name})
            if mongo_item:
                mongo_item['faces_number'] = len(mongo_item.get('faces')) + 1
                if mongo_item['faces_number'] <= 5:
                    mongo_item.get('faces').append(new_face)
                    db.faces.save(mongo_item)

        flash('Assessment Added', 'success')

        tracker.__init__()

        return redirect(url_for('dashboard'))
    except Exception as e:
        print('Exception in incorrect_guess(): {}, {}'.format(str(e), str(e.args)))
        form = ImageForm()
        return render_template('try_image.html', form=form)


# True name form
class NameForm(Form):
    true_name = StringField('True Name', [validators.Length(min=1, max=200)])


# If guess was incorrect
@app.route('/assessment/incorrect_guess', methods=['GET', 'POST'])
@is_logged_in
def incorrect_guess():
    form = NameForm(request.form)
    try:
        if request.method == 'POST' and form.validate():
            tracker.true_name = form.true_name.data

            archive = {
                    'name': tracker.name,
                    'confidence': tracker.confidence,
                    'author': session['username'],
                    'create_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'true_name': tracker.true_name,
                    'no_faces': tracker.no_faces,
                    'multiple_faces': tracker.multiple_faces,
                    'low_confidence': tracker.low_confidence,
                    'precise_prediction': tracker.precise_prediction,
                    'error': False,
                    'to_show': True,
                    }
            archive_id = db.archive.save(archive)

            # Add to mongo
            new_face = {
                         'author': session['username'],
                         'guess': tracker.name,
                         'confidence': tracker.confidence,
                         'descriptor': tracker.descriptor,
                         'archive_id': archive_id,
            }

            if (not tracker.multiple_faces) and (not tracker.no_faces) and \
                    (not tracker.precise_prediction):
                mongo_item = db.faces.find_one({'name': tracker.true_name})
                if mongo_item:
                    mongo_item['faces_number'] += 1
                    if mongo_item['faces_number'] <= 5:
                        mongo_item.get('faces').append(new_face)
                        db.faces.save(mongo_item)
                else:
                    mongo_item = {'name': tracker.true_name,
                                  'index': -1,
                                  'faces_number': 1,
                                  'faces': [new_face]
                                  }
                    db.faces.save(mongo_item)

            flash('Assessment Added', 'success')

            tracker.__init__()

            return redirect(url_for('dashboard'))
        return render_template('incorrect_guess.html', form=form)
    except Exception as e:
        print('Exception in incorrect_guess(): {}, {}'.format(str(e), str(e.args)))
        form = ImageForm()
        return render_template('try_image.html', form=form)


# Delete image
@app.route('/delete_image/<string:id>', methods=['POST'])
@is_logged_in
def delete_image(id):

    photo = db.archive.find_one({'_id': ObjectId(id)})
    true_name = 'no_name'
    if photo:
        print(photo)
        true_name = photo.get('true_name')

    db.archive.delete_one({'_id': ObjectId(id)})

    user = db.faces.find_one({'name': true_name})
    if user:
        for face in user.get('faces'):
            if face.get('archive_id') == ObjectId(id):
                user.get('faces').remove(face)
        user['faces_number'] = len(user.get('faces'))
        db.faces.save(user)

        flash('Image Deleted', 'success')

    return redirect(url_for('images'))


# Hide image
@app.route('/hide_image/<string:id>', methods=['POST'])
@is_logged_in
def hide_image(id):

    photo = db.archive.find_one({'_id': ObjectId(id)})
    photo['to_show'] = False
    db.archive.save(photo)

    flash('Image has been hidden', 'success')

    return redirect(url_for('images'))


if __name__ == '__main__':
    app.secret_key = config.secret_key
    app.run(debug=True)
