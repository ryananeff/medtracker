from flask import Flask, request, redirect, send_from_directory, Response, stream_with_context, url_for, render_template
from requests.auth import HTTPBasicAuth
from medtracker.config import *

import twilio.twiml
from twilio.rest import TwilioRestClient

from flask.ext.mail import Mail
import flask.ext.login as flask_login

from ftplib import FTP_TLS
from flask import flash
from itsdangerous import URLSafeTimedSerializer
ts = URLSafeTimedSerializer(flask_secret_key)

#Flask init
app = Flask(__name__, static_folder='')
app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = flask_secret_key
app.debug = True

mail = Mail(app)


client = TwilioRestClient(twilio_AccountSID, twilio_AuthToken)
auth_combo=(twilio_AccountSID, twilio_AuthToken)

from medtracker.database import db_session 	# to make sqlalchemy DB calls
import medtracker.views				# web pages
import medtracker.triggers

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()
