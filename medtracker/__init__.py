from flask import *
from flask_caching import Cache
from requests.auth import HTTPBasicAuth
import random, string, pytz, sys, random, urllib.parse, datetime, os
from werkzeug.utils import secure_filename
from itertools import groupby
from delta import html as delta_html #https://github.com/forgeworks/quill-delta-python
from flask_login import login_user, logout_user, current_user
from medtracker.config import *
from flask_qrcode import QRcode
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

import twilio.twiml
from twilio.rest import TwilioRestClient

from flask_mail import Mail
import flask_login as flask_login

from ftplib import FTP_TLS
from flask import flash
from itsdangerous import URLSafeTimedSerializer

#from flask_debugtoolbar import DebugToolbarExtension

ts = URLSafeTimedSerializer(flask_secret_key)

#Flask init
app = Flask(__name__, static_folder='')
cache = Cache(app,config={'CACHE_TYPE': 'filesystem',
    'CACHE_DIR':'cache/',
    'CACHE_DEFAULT_TIMEOUT':60*60})
app.config["APPLICATION_ROOT"] = "/"
app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SECRET_KEY'] = flask_secret_key
app.config['WTF_CSRF_ENABLED']=True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600
#app.config["DEBUG_TB_PROFILER_ENABLED"] = True
#app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False
#app.debug = True
#toolbar = DebugToolbarExtension(app)

app.debug=False


#init db
db = SQLAlchemy(app)
db_session = db.session

migrate = Migrate(app,db,render_as_batch=True)

app.config.update(
	#EMAIL SETTINGS
	MAIL_SERVER=mail_server_address,
	MAIL_PORT=465,
	MAIL_USE_SSL=True,
	MAIL_USERNAME = mail_server_user,
	MAIL_PASSWORD = mail_server_password
)
mail = Mail(app)

qrcode = QRcode(app)

from .momentjs import momentjs
app.jinja_env.globals['momentjs'] = momentjs

mail = Mail(app)

client = TwilioRestClient(twilio_AccountSID, twilio_AuthToken)
auth_combo=(twilio_AccountSID, twilio_AuthToken)

from medtracker.views import *				# web pages
from medtracker.triggers import *

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

