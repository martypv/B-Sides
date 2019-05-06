import os,random,string
from flask import Flask, render_template, session, redirect, url_for, jsonify, request
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
    room_name = db.Column(db.String(64), index=True)
    room_code = db.Column(db.String(64), index=True)
 #   playlist_uri = db.Column(db.String(200), index=True)
 #   cur_track_name = db.Column(db.String(200), index=True)
 #   cur_track_im = db.Column(db.String(200), index=True)
    vote_a = db.Column(db.Integer, index=True)
    vote_b = db.Column(db.Integer, index=True)
    vote_open = db.Column(db.BOOLEAN, index=True)

    def __repr__(self):
        return '<Room {}>'.format(self.code)

# ---------- FORM CLASSES --------------

class joinForm(FlaskForm):
    code = StringField('Room Code: ', validators=[DataRequired()])
    submit = SubmitField('OK')

class createForm(FlaskForm):
    name = StringField('Room Name: ', validators=[DataRequired()])
    code = StringField('Room Code: ', validators=[DataRequired()])
    submit = SubmitField('Ready')

class subForm(FlaskForm):
    submit = SubmitField('Start')

class voteForm(FlaskForm):
    pick_a = SubmitField('A')
    pick_b = SubmitField('B')

# ---------- APP ROUTES/PAGES ----------

@app.route('/', methods=['GET', 'POST'])
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
        temp_code = form.code.data
        temp = Room.query.filter_by(room_code=form.code.data).first()
        if temp is not None:
            return redirect('/room/viewer/' + form.code.data)
        return redirect(url_for('joinRoom'))
    return render_template('join.html', form=form)

@app.route('/create', methods=['GET', 'POST'])
def createRoom():
    form = createForm()
    temp_name = ""
    temp_code = ""
    if form.validate_on_submit():
        temp_name = form.name.data
        temp_code = form.code.data
        if Room.query.filter_by(room_code=temp_code).first() is None:
            room = Room(room_name=temp_name, room_code=temp_code, vote_a=0, vote_b=0, vote_open=True)
            db.session.add(room)
            db.session.commit()
            return redirect(url_for('set_playlist', code=temp_code))
    return render_template('create.html', form=form)

@app.route('/room/viewer/<code>', methods=['GET', 'POST'])
def viewRoom(code):
    form = voteForm()
    name = Room.query.filter_by(room_code=code).first().room_name
    if form.validate_on_submit():
        if form.pick_a.data:
            val_a = Room.query.filter_by(room_code=code).first().vote_a
            val_a = val_a + 1
            Room.query.filter_by(room_code=code).first().vote_a = val_a
            print(Room.query.filter_by(room_code=code).first().vote_a)
        if form.pick_b.data:
            val_b = Room.query.filter_by(room_code=code).first().vote_b
            val_b += 1
            Room.query.filter_by(room_code=code).first().vote_b = val_b
    return render_template('view_room.html', code=code, name=name, form=form)

@app.route('/room/play/<code>', methods=['GET', 'POST'])
def playRoom(code):
    done = Room.query.filter_by(room_code=code).first().vote_open
    votes_a = Room.query.filter_by(room_code=code).first().vote_a
    votes_b = Room.query.filter_by(room_code=code).first().vote_b
    # if done is False:
    #     Room.query.filter_by(room_code=code).first().vote_a = 0
    #     Room.query.filter_by(room_code=code).first().vote_b = 0
    #     Room.query.filter_by(room_code=code).first().vote_open = True
    return render_template('app_player.html', code=code, vote_a=votes_a, vote_b=votes_b, done=done)

@app.route('/set_playlist/<code>', methods=['GET', 'POST', 'PUT'])
@app.route('/set_playlist', methods=['GET', 'POST', 'PUT'])
def set_playlist(code):
    db.session.commit()
    form = subForm()
    if form.validate_on_submit():
        # uri = request.json
        # Room.query.filter_by(room_code=code).first().playlist_uri = uri
        return redirect(url_for('playRoom', code=code))
    return render_template('set_playlist.html', code=code, form=form)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/nothing/')
def nothing(name, code):
    return render_template('nothing.html', name=name, code=code)


if __name__ == '__main__':
    app.run()
