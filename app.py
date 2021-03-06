from __future__ import print_function
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
import pymongo
from bson.objectid import ObjectId
from datetime import datetime
from config import config
# import telegram  # pip install python-telegram-bot --upgrade
from telegram.ext import Updater  # pip install python-telegram-bot[socks]


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


facecom = FaceComparator()
REQUEST_KWARGS = config.request_kwargs
updater = Updater(config.telegram_token, request_kwargs=REQUEST_KWARGS)


# Index
@app.route('/')
def index():
    return render_template('home.html')


# About
@app.route('/about')
def about():
    return render_template('about.html')


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


def restore_session(session):
        session['descriptor'] = config.tracker.get('descriptor')
        session['name'] = config.tracker.get('name')
        session['true_name'] = config.tracker.get('true_name')
        session['confidence'] = config.tracker.get('confidence')
        session['multiple_faces'] = config.tracker.get('multiple_faces')
        session['no_faces'] = config.tracker.get('no_faces')
        session['faces_number'] = config.tracker.get('faces_number')
        session['low_confidence'] = config.tracker.get('low_confidence')
        session['precise_prediction'] = config.tracker.get('precise_prediction')
        session['error_added'] = config.tracker.get('error_added')
        session['candidates'] = config.tracker.get('candidates')
        session['faces'] = config.tracker.get('faces')
        return session


def send_image_to_telegram(image):
    '''Send picture to telegram account'''

    try:
        document = open(image, 'rb')
        # updater.bot.send_chat_action(config.my_telegram_id, 'upload_document')
        updater.bot.send_document(config.my_telegram_id,
                                  document,
                                  timeout=config.telegram_timeout)
        document.close()
    except Exception as e:
        print(e.args)


def send_assessment_to_telegram(session):
    '''Send info about session to telegram'''

    try:
        text = 'User: {}\n\
        Time: {}\n\
        Faces number: {}\n\
        Guess was: {}\n\
        Confidence: {}\n\
        Parameters\n\
        Multiple faces: {}\n\
        No faces: {}\n\
        Low confidence: {}\n\
        Precise prediction (already in DB): {}\n\
        '.format(
            session.get('username'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            session.get('faces_number'),
            ', '.join(session.get('faces')),
            session.get('confidence'),
            session.get('multiple_faces'),
            session.get('no_faces'),
            session.get('low_confidence'),
            session.get('precise_prediction')
            )
        updater.bot.send_message(config.my_telegram_id,
                                 text,
                                 timeout=config.telegram_timeout)
    except Exception as e:
        print(e.args)


def send_result_to_telegram(session, text):
    '''Send info about assessment result to telegram'''

    try:
        text = '{}\n\
        User: {}\n\
        Time: {}\n\
        Name: {}\n\
        Guess was: {}\n\
        '.format(
            text,
            session.get('username'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            session.get('true_name'),
            session.get('name')
            )
        updater.bot.send_message(config.my_telegram_id,
                                 text,
                                 timeout=config.telegram_timeout)
    except Exception as e:
        print(e.args)


# Images
@app.route('/images')
@is_logged_in
def images():
    if session.get('rights') == 'admin':
        result = db.archive.find().sort('create_date', -1)
    else:
        result = db.archive.find({'author': session['username']}).sort('create_date', -1)

    if result.count() > 0:
        return render_template('images.html', images=result)
    else:
        msg = 'No images found'
        return render_template('images.html', msg=msg)


# Admin images
@app.route('/admin_images')
@is_logged_in
def admin_images():

    result = db.archive.find({'author': session['username']}).sort('create_date', -1)

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
    # name = StringField('Name', [validators.Length(min=1, max=50)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    # email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')])
    confirm = PasswordField('Confirm Password')


# User register
@app.route('/register/', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        # name = form.name.data
        # email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        user = {'username': username, 'password': password}

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
                if session['username'] in config.admin_names:
                    pass
                    session['rights'] = 'admin'
                else:
                    session['rights'] = 'user'

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid password'
                return render_template('login.html', error=error)
        else:
            error = 'Username not found'
            return render_template('login.html', error=error)

    return render_template('login.html')


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


def save_error_to_db():
    print('Error; no_faces: {}; multiple_faces: {}, precise_prediction: {}\
        '.format(session.get('no_faces'),
                 session.get('multiple_faces'),
                 session.get('precise_prediction')
                 ))
    archive = {
        'name': session['name'],
        'confidence': session['confidence'],
        'author': session['username'],
        'create_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'true_name': session['true_name'],
        'no_faces': session['no_faces'],
        'multiple_faces': session['multiple_faces'],
        'low_confidence': session['low_confidence'],
        'precise_prediction': session['precise_prediction'],
        'faces_number': session['faces_number'],
        'error': True,
        'to_show': True
        }
    if session.get('multiple_faces'):
        if session.get('faces'):
            archive['name'] = session.get('faces')[0]
            archive['faces'] = session.get('faces')
    db.archive.save(archive)


# Assessment
@app.route('/assessment/')
def assessment():
    try:
        error = False
        no_faces = session.get('no_faces')
        multiple_faces = session.get('multiple_faces')
        low_confidence = session.get('low_confidence')
        if no_faces:
            text = "I don't see any faces here... :("
            result_code = 0
            error = True
        elif multiple_faces:
            result_code = 2
            error = True
            if not session['faces']:
                # text = "I see {} faces here. But I actually don't know any of them!".format(session['faces_number'])
                text = "I haven't seen anybody from this photo before..."
            elif len(session.get('faces')) == len(session.get('candidates')):
                # text = "I see {} faces here. I guess they are: ".format(session['faces_number'])
                text = 'Here are people, that I know on this photo: '
            else:
                if len(session.get('faces')) > 1:
                    # text = "I see {} faces here. I guess {} of them are: ".format(session['faces_number'], len(session.get('faces')))
                    text = 'I guess {} faces on this photo are: '.format(len(session.get('faces')))
                else:
                    # text = "I see {} faces here. I guess one of them is: ".format(session['faces_number'])
                    text = 'I have seen one person from this photo before! That is: '
        elif low_confidence:
            result_code = 3
            text = "This person doesn't look familiar..."
        else:
            result_code = 1
            text = 'It seems to me, this is a photo of {}'.format(session.get('name'))
        if error:
            if not session['error_added']:
                save_error_to_db()
                session['error_added'] = True
        flash('Assessment page', 'success')
        return render_template('assessment.html', result_code=result_code, text=text, faces=session.get('faces'))
    except Exception as e:
        print(e, e.args)
        return render_template('try_image.html')


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

    facecom.main(image)
    to_return = (facecom.most_likeleys, facecom.descriptors)
    facecom.restore_default()
    return to_return


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
        restore_session(session)
        form = ImageForm()
        if request.method == 'POST':
            if 'image' not in request.files:
                flash('No file found')
            else:
                file = request.files['image']
                filename = 'temp/'+secure_filename(file.filename)
                file.save(filename)
                send_image_to_telegram(filename)

            try:
                most_likeleys, descriptors = recognize(file)
                if len(descriptors) > 1:
                    session['multiple_faces'] = True
                    session['candidates'] = most_likeleys
                elif len(descriptors) == 1:
                    difference, session["name"] = most_likeleys[0]
                    session['faces'] = [session['name']]
                    session['descriptor'] = list(descriptors[0])
            except Exception as e:
                print(e)
                difference = 1
                session['name'] = "Not assessed"
                descriptors = []

            session['faces_number'] = len(descriptors)
            if not descriptors:
                session['no_faces'] = True
            if session['faces_number'] == 1:
                if difference == 0:
                    session['precise_prediction'] = True
                session['confidence'] = confidence_calculator(difference)
                if session['confidence'] < confidence_calculator(config.threshold):
                    session['low_confidence'] = True
                    session['faces'] = []

            elif session['faces_number'] > 1:
                session['faces'] = [i[1] for i in session.get('candidates')
                                    if confidence_calculator(i[0]) > confidence_calculator(config.threshold)]

            send_assessment_to_telegram(session)
            return redirect(url_for('assessment'))
        return render_template('try_image.html', form=form)
    except Exception as e:
        print('Exception in try_image(): {}, {}'.format(str(e), str(e.args)))
        return render_template('try_image.html')


# If guess was correct
@app.route('/assessment/correct_guess', methods=['POST'])
@is_logged_in
def correct_guess():
    try:
        session['true_name'] = session['name']

        archive = {
                'name': session['name'],
                'confidence': session['confidence'],
                'author': session['username'],
                'create_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'true_name': session['true_name'],
                'no_faces': session['no_faces'],
                'multiple_faces': session['multiple_faces'],
                'low_confidence': session['low_confidence'],
                'precise_prediction': session['precise_prediction'],
                'faces_number': session['faces_number'],
                'error': False,
                'to_show': True,
                }
        archive_id = db.archive.save(archive)

        # Add to mongo
        new_face = {
            'author': session['username'],
            'guess': session['name'],
            'confidence': session['confidence'],
            'descriptor': session['descriptor'],
            'archive_id': archive_id
            }

        if (not session['multiple_faces']) and (not session['no_faces']) and \
                (not session['low_confidence']) and (not session['precise_prediction']):
            mongo_item = db.faces.find_one({'name': session['true_name']})
            if mongo_item:
                mongo_item['faces_number'] = len(mongo_item.get('faces')) + 1
                if mongo_item['faces_number'] <= 5:
                    mongo_item.get('faces').append(new_face)
                    db.faces.save(mongo_item)
        send_result_to_telegram(session, text='Correct Guess!')

        flash('Assessment Added', 'success')

        restore_session(session)

        return redirect(url_for('dashboard'))
    except Exception as e:
        print('Exception in correct_guess(): {}, {}'.format(str(e), str(e.args)))
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
            session['true_name'] = form.true_name.data

            archive = {
                    'name': session['name'],
                    'confidence': session['confidence'],
                    'author': session['username'],
                    'create_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'true_name': session['true_name'],
                    'no_faces': session['no_faces'],
                    'multiple_faces': session['multiple_faces'],
                    'low_confidence': session['low_confidence'],
                    'precise_prediction': session['precise_prediction'],
                    'faces_number': session['faces_number'],
                    'error': False,
                    'to_show': True,
                    }
            archive_id = db.archive.save(archive)

            # Add to mongo
            new_face = {
                         'author': session['username'],
                         'guess': session['name'],
                         'confidence': session['confidence'],
                         'descriptor': session['descriptor'],
                         'archive_id': archive_id,
            }

            if (not session['multiple_faces']) and (not session['no_faces']) and \
                    (not session['precise_prediction']):
                mongo_item = db.faces.find_one({'name': session['true_name']})
                if mongo_item:
                    mongo_item['faces_number'] += 1
                    if mongo_item['faces_number'] <= 5:
                        mongo_item.get('faces').append(new_face)
                        db.faces.save(mongo_item)
                else:
                    mongo_item = {'name': session['true_name'],
                                  'index': -1,
                                  'faces_number': 1,
                                  'faces': [new_face]
                                  }
                    if len(session['true_name'].split()) <= 1:
                        mongo_item['display_name'] = session['true_name'].split()[0]
                    elif len(session['true_name'].split()) > 1:
                        mongo_item['display_name'] = session['true_name'].split()[0] + ' ' + session['true_name'].split()[1][0] + '.'
                    db.faces.save(mongo_item)

            send_result_to_telegram(session, text='Inorrect Guess!')

            flash('Assessment Added', 'success')

            restore_session(session)

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


# Delete person
@app.route('/delete_person/<string:id>', methods=['POST'])
@is_logged_in
def delete_person(id):

    db.faces.delete_one({'_id': ObjectId(id)})
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.secret_key = config.secret_key
    app.run(debug=False)
