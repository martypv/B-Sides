from flask import Flask, render_template
from flask_bootstrap import Bootstrap

app = Flask(__name__)

bootstrap = Bootstrap(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(404)
def notfound(e):
    return render_template('error404.html'), 404


@app.errorhandler(500)
def servererror(e):
    return render_template('error500.html'), 500


if __name__ == '__main__':
    app.run()
