import os,random,string
from flask import Flask, render_template, session, redirect, url_for
from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, PasswordField
from wtforms.validators import DataRequired
from flask_sqlalchemy import SQLAlchemy

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pleasedont'

bootstrap = Bootstrap(app)

# ---------- DATABASE CLASSES ----------


# ---------- FORM CLASSES --------------

class joinForm(FlaskForm):
    code = StringField('Room Code: ', validators=[DataRequired()])
    submit = SubmitField('OK')

# ---------- APP ROUTES/PAGES ----------

@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(404)
def notfound(e):
    return render_template('error404.html'), 404


@app.errorhandler(500)
def servererror(e):
    return render_template('error500.html'), 500

@app.route('/frame')
def frame():
    return render_template('frame.html')

@app.route('/join', methods=['GET', 'POST'])
def joinRoom():
    form = joinForm()
    if form.validate_on_submit():
        session['code'] = form.code.data
        return redirect(url_for('joinRoom'))
    return render_template('join.html', form=form, code=session.get('code'))


if __name__ == '__main__':
    app.run()
