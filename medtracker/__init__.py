from flask import *
from requests.auth import HTTPBasicAuth
import random, string, pytz, sys, random, urllib.parse, datetime, os
from werkzeug.utils import secure_filename
from itertools import groupby
from delta import html as delta_html #https://github.com/forgeworks/quill-delta-python
from flask_login import login_user, logout_user, current_user
from medtracker.config import *
from flask_qrcode import QRcode

import twilio.twiml
from twilio.rest import TwilioRestClient

from flask_mail import Mail
import flask_login as flask_login

from ftplib import FTP_TLS
from flask import flash
from itsdangerous import URLSafeTimedSerializer
ts = URLSafeTimedSerializer(flask_secret_key)

#Flask init
app = Flask(__name__, static_folder='')
app.config["APPLICATION_ROOT"] = "/medtracker"
app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['REMEMBER_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SECRET_KEY'] = flask_secret_key
app.config['WTF_CSRF_ENABLED']=False
app.debug = True

qrcode = QRcode(app)

from .momentjs import momentjs
app.jinja_env.globals['momentjs'] = momentjs

mail = Mail(app)

client = TwilioRestClient(twilio_AccountSID, twilio_AuthToken)
auth_combo=(twilio_AccountSID, twilio_AuthToken)

from medtracker.database import db_session 	# to make sqlalchemy DB calls
from medtracker.views import *				# web pages
from medtracker.triggers import *

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()
 
