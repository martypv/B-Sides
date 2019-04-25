import os,random,string
from flask import Flask, render_template, session, redirect, url_for
from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, PasswordField
from wtforms.validators import DataRequired
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

bootstrap = Bootstrap(app)

# ---------- DATABASE CLASSES ----------

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True)
    code = db.Column(db.String(120), index=True, unique=True)
    playlist = db.relationship('Playlist', backref='author', lazy='dynamic')

    def __repr__(self):
        return '<Room {}>'.format(self.code)

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    playlist_uri = db.Column(db.String(200), index=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    current_track = db.Column(db.String(200), index=True)

    def __repr__(self):
        return '<Playlist {}>'.format(self.playlist_uri)

# ---------- FORM CLASSES --------------

class joinForm(FlaskForm):
    code = StringField('Room Code: ', validators=[DataRequired()])
    submit = SubmitField('OK')

class createForm(FlaskForm):
    name = StringField('Room Name: ', validators=[DataRequired()])
    code = StringField('Room Code: ', validators=[DataRequired()])
    submit = SubmitField('Ready')

# ---------- APP ROUTES/PAGES ----------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/player')
def player():
    return render_template('player.html')


@app.errorhandler(404)
def notfound(e):
    return render_template('error404.html'), 404


@app.errorhandler(500)
def servererror(e):
    return render_template('error500.html'), 500

@app.route('/frame')
def frame():
    return render_template('frame.html')

@app.route('/playlists')
def playlists():
    return render_template('playlists.html')


@app.route('/join', methods=['GET', 'POST'])
def joinRoom():
    form = joinForm()
    if form.validate_on_submit():
        session['code'] = form.code.data
        temp = Room.query.filter_by(code=form.code.data).first()
        if temp is not None:
            return redirect('/room/viewer/' + form.code.data)
        return redirect(url_for('joinRoom'))
    return render_template('join.html', form=form, code=session.get('code'))

@app.route('/room/create', methods=['GET', 'POST'])
def createRoom():
    form = createForm()
    if form.validate_on_submit():
        session['name'] = form.name.data
        session['code'] = form.code.data
        if Room.query.filter_by(code=form.code.data).first() is None:
            room = Room(name=form.name.data, code=form.code.name)
            db.session.add(room)
            db.session.commit()
    return render_template('join.html', form=form, name=session.get('name'), code=session.get('code'))

@app.route('/room/viewer/<code>')
def viewRoom(code):
    return render_template('')

@app.route('/room/play/<code>')
def viewPlayRoom(code):
    return render_template('')


@app.route('/login')
def temp():
    return render_template('login.html')


if __name__ == '__main__':
    app.run()
