from medtracker.database import db
from medtracker.config import *
from sqlalchemy_utils import EncryptedType, ChoiceType
from datetime import datetime
from passlib.apps import custom_app_context as pwd_context

TEXT = 'text'
YES_NO = 'yes-no'
NUMERIC = 'numeric'
RADIO = 'radio'
SELECT = 'select'

QUESTION_KIND_CHOICES = (
	(TEXT, 'Type your answer'),
	(YES_NO, 'Choose YES (Y) or NO (N)'),
	(NUMERIC, 'Choose 1 - 10'),
	(RADIO, 'Select one'),
	(SELECT, 'Select one or more')
)

VOICE = 'voice'
SMS = 'sms'
EMAIL = 'email'
CURL = 'curl'

TRIGGER_KIND_CHOICES = (
	(VOICE, 'Call a phone number'),
	(SMS, 'Send a text or picture message'),
	(EMAIL, 'Send an email'),
	(CURL, 'POST to a URL')
)

class Progress(db.Model):
	__tablename__ = 'progress'
	id = db.Column(db.Integer, primary_key=True)
	user = db.Column(EncryptedType(db.String, flask_secret_key))
	task = db.Column(db.String)
	iterator = db.Column(db.Integer)
	parent_id = db.Column(db.String) # this is the uniq_id?
	complete = db.Column(db.Integer)

	def __init__(self, user='', task='', iterator=0, parent_id='', complete=0):
		self.user = str(user)
		self.task = str(task)
		self.iterator = int(iterator)
		self.parent_id = str(parent_id)
		self.complete = int(complete)
	
class Survey(db.Model):
	__tablename__ = 'survey'
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String)
	description = db.Column(db.String)
	questions = db.relationship("Question", backref='survey', cascade="all, delete-orphan")
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	read_public = db.Column(db.Boolean)
	edit_public = db.Column(db.Boolean)

	def __str__(self):
		return '%s' % self.title
	
	def __init__(self, title=None, description=None):
		self.title = title
		self.description=description

class Question(db.Model):
	__tablename__ = 'question'
	
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	image = db.Column(db.String)
	kind = db.Column(ChoiceType(QUESTION_KIND_CHOICES))
	survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'))
	question = db.relationship("Survey", backref='question')
	trigger_id = db.Column(db.Integer, db.ForeignKey('trigger.id'))
	trigger = db.relationship("Trigger", backref='question')
	survey_pos = db.column(db.Integer)
	responses = db.relationship("QuestionResponse", backref='question')

	def __str__(self):
		return '%s' % self.body
	
	def __init__(self, body=None, image=None, kind=None, survey_id=None):
		self.body = body
		self.image = image
		self.kind = kind
		self.survey_id = survey_id

class QuestionMeta(db.Model):
	__tablename__ = 'question_meta'
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	
	def __init__(self, body=None, question=None):
		self.body = body
		self.question_id = question_id

class QuestionResponse(db.Model):
	__tablename__ = 'question_response'
	id = db.Column(db.Integer, primary_key=True)
	response = db.Column(EncryptedType(db.String, flask_secret_key))
	time = db.Column(EncryptedType(db.DateTime, flask_secret_key))
	uniq_id = db.Column(EncryptedType(db.String, flask_secret_key))
	session_id = db.Column(EncryptedType(db.String, flask_secret_key))
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	_question = db.relationship("Question", backref='_response')

	def __str__(self):
		return '%s' % self.response
	
	def __init__(self, response=None, uniq_id=None, session_id=None, question_id=None, time=datetime.utcnow()):
		self.response = response
		self.uniq_id = uniq_id
		self.session_id = session_id
		self.question_id = question_id
		self.time = time

class Trigger(db.Model):
	__tablename__ = 'trigger'
	
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String)
	criteria = db.Column(db.String)
	kind = db.Column(ChoiceType(TRIGGER_KIND_CHOICES))
	recipients = db.Column(db.String)
	after_function = db.Column(db.String)
	questions = db.relationship("Question", backref='_trigger')
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	read_public = db.Column(db.Boolean)
	edit_public = db.Column(db.Boolean)

	def __str__(self):
		return '%s' % self.body
	
	def __init__(self, body=None, kind=None, criteria=None, recipients=None, af=None):
		self.title = body
		self.kind = kind
		self.criteria = criteria
		self.recipients = recipients
		self.after_function = af

class User(db.Model):
    """A user capable of listening to voicemails"""
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(EncryptedType(db.String, flask_secret_key), unique=True)
    username = db.Column(EncryptedType(db.String, flask_secret_key), unique=True)
    name = db.Column(EncryptedType(db.String, flask_secret_key))
    password_hash = db.Column(db.String(256))
    active = db.Column(db.Boolean, default=False)
    google_token = db.Column(EncryptedType(db.String, flask_secret_key))
    authenticated = db.Column(db.Boolean, default=False)
    surveys = db.relationship("Survey", backref='user', lazy='dynamic')
    triggers = db.relationship("Trigger", backref='user', lazy='dynamic')
    responses = db.relationship("QuestionResponse", backref='user', lazy='dynamic')
    patients = db.relationship("Patient", backref='user', lazy='dynamic')

    def is_active(self):
        """True, as all users are active."""
        return True

    def get_id(self):
        """Return the id to satisfy Flask-Login's requirements."""
        return self.id

    def is_authenticated(self):
        """Return True if the user is authenticated."""
        return self.authenticated

    def is_anonymous(self):
        """False, as anonymous users aren't supported."""
        return False

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

class Patient(db.Model):
	'''A patient record capable of taking surveys'''
	__tablename__= "patients"

	id = db.Column(db.Integer, primary_key=True)
	mrn = db.Column(EncryptedType(db.String, flask_secret_key))
	fullname = db.Column(EncryptedType(db.String, flask_secret_key))
	dob = db.Column(EncryptedType(db.Date, flask_secret_key))
	phone = db.Column(EncryptedType(db.String, flask_secret_key))
	email = db.Column(EncryptedType(db.String, flask_secret_key))
	notes = db.Column(EncryptedType(db.String, flask_secret_key))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))