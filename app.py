from flask import Flask, render_template, flash, redirect, url_for, session
from flask import request, logging
from flask_mysqldb import MySQL
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from flask_wtf.file import FileField, FileRequired, FileAllowed
from flask_wtf import FlaskForm
from passlib.hash import sha256_crypt
from functools import wraps
from werkzeug.utils import secure_filename
import os
from face_recognizer import FaceComparator
import json
import pymongo

app = Flask(__name__)

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '3630000'
app.config['MYSQL_DB'] = 'myflaskapp'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
# init MYSQL
mysql = MySQL(app)

app.config['UPLOADED_PHOTOS_DEST'] = os.getcwd()
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)
patch_request_class(app)  # set maximum file size, default is 16MB
client = pymongo.MongoClient(host='localhost', port=27017)
db = client.faces


class Tracker():
    '''Tracker of assessment results'''

    def __init__(self):
        self.descriptor = []
        self.name = ''
        self.true_name = ''
        self.author = ''
        self.confidence = 2.0
        self.assessment = {}
        self.multiple_faces = False
        self.no_faces = False
        self.faces_number = 0
        self.low_confidence = False


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
    # Create cursor
    cur = mysql.connection.cursor()

    # Get images
    result = cur.execute("SELECT * FROM images")

    images = cur.fetchall()

    if result > 0:
        return render_template('images.html', images=images)
    else:
        msg = 'No images found'
        return render_template('images.html', msg=msg)


# Single image
@app.route('/images/<string:id>/')
def image(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Get images
    result = cur.execute("SELECT * FROM images WHERE id = %s", [id])

    image = cur.fetchone()

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

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)",
                    (name, email, username, password))

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

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

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if result > 0:
            # Get srored hash
            data = cur.fetchone()
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
            # Close connection
            cur.close()
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


# Assessment
@app.route('/assessment/<string:assessment>')
def assessment(assessment):
    form = ImagePostForm()
    if assessment:
        assessment = json.loads(assessment)
        no_faces = assessment.get('no_faces')
        multiple_faces = assessment.get('multiple_faces')
        if no_faces:
            text = "I don't see any faces here... :("
        elif multiple_faces:
            text = "I see {} faces here. One of them is definately {}!".format(tracker.faces_number, assessment.get('person'))
        else:
            text = 'It seems to me, this is a photo of {}'.format(assessment.get('person'))
        resemblance = confidence_calculator(assessment.get('difference'))
        if resemblance < 45:
            text = "This person doesn't look familiar..."
            tracker.low_confidence = True
        flash('Assessment page', 'success')
        return render_template('assessment.html', resemblance=resemblance, text=text)  # msg=msg,
    text = "This person doesn't look familiar..."
    return render_template('assessment.html', resemblance=0, text=text)


# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    # Create cursor
    cur = mysql.connection.cursor()

    # Get images
    result = cur.execute("SELECT * FROM images")

    images = cur.fetchall()

    if result > 0:
        return render_template('dashboard.html', images=images)
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
        if not descriptor:
            tracker.no_faces = True

        tracker.name = assessment.get('person')
        tracker.confidence = confidence_calculator(assessment.get('difference'))
        if not tracker.no_faces:
            tracker.descriptor = list(descriptor[0])
        if len(descriptor) > 1:
            tracker.multiple_faces = True
        tracker.faces_number = len(descriptor)

        assessment['no_faces'] = tracker.no_faces
        assessment['multiple_faces'] = tracker.multiple_faces

        assessment = json.dumps(assessment)
        return redirect(url_for('assessment', assessment=assessment))

    return render_template('try_image.html', form=form)


# If guess was correct
@app.route('/assessment/correct_guess', methods=['POST'])
@is_logged_in
def correct_guess():
    tracker.true_name = tracker.name

    # Add to mongo
    new_face = {
        'author': session['username'],
        'guess': tracker.name,
        'confidence': tracker.confidence,
        'sql_id': 0,
        'descriptor': tracker.descriptor
        }

    if (not tracker.multiple_faces) and (not tracker.no_faces) and (not tracker.low_confidence):
        mongo_item = db.faces.find_one({'name': tracker.true_name})
        if mongo_item:
            mongo_item['faces_number'] += 1
            if mongo_item['faces_number'] <= 5:
                mongo_item.get('faces').append(new_face)
                db.faces.save(mongo_item)

    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("INSERT INTO images(name, confidence, author, true_name) VALUES(%s, %s, %s, %s)",
                (tracker.name, tracker.confidence, session['username'], tracker.true_name))
    # Commit to DB
    mysql.connection.commit()

    # Close connection
    cur.close()

    flash('Assessment Added', 'success')

    tracker.__init__()

    return redirect(url_for('dashboard'))


# True name form
class NameForm(Form):
    true_name = StringField('True Name', [validators.Length(min=1, max=200)])


# If guess was incorrect
@app.route('/assessment/incorrect_guess', methods=['GET', 'POST'])
@is_logged_in
def incorrect_guess():
    form = NameForm(request.form)
    if request.method == 'POST' and form.validate():
        tracker.true_name = form.true_name.data

        # Add to mongo
        new_face = {
                     'author': session['username'],
                     'guess': tracker.name,
                     'confidence': tracker.confidence,
                     'sql_id': 0,
                     'descriptor': tracker.descriptor
        }

        if (not tracker.multiple_faces) and (not tracker.no_faces):
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

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute
        cur.execute("INSERT INTO images(name, confidence, author, true_name) VALUES(%s, %s, %s, %s)",
                    (tracker.name, tracker.confidence, session['username'], tracker.true_name))
        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash('Assessment Added', 'success')

        tracker.__init__()

        return redirect(url_for('dashboard'))
    return render_template('incorrect_guess.html', form=form)


# Delete article
@app.route('/delete_image/<string:id>', methods=['POST'])
@is_logged_in
def delete_image(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Execute
    cur.execute("DELETE FROM images WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    # Close connection
    cur.close()

    flash('Image Deleted', 'success')

    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.secret_key = 'secret123'
    app.run(debug=True)
