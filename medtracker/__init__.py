from flask import Flask, request, redirect, send_from_directory, Response, stream_with_context, url_for, render_template
from requests.auth import HTTPBasicAuth
from medtracker.config import *
from flask.ext.mail import Mail

#Flask init
app = Flask(__name__, static_folder='')
app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = flask_secret_key
app.debug = True

mail = Mail(app)

from medtracker.database import db_session 	# to make sqlalchemy DB calls
import medtracker.models			# database models
import medtracker.views				# web pages 
import medtracker.backgroundtasks		# sending push reminders

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()
