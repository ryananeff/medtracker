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
	(SELECT, 'Select one or more options'),
	(RADIO, 'Choose one option')
)

VOICE = 'voice'
SMS = 'sms'
EMAIL = 'email'
CURL = 'curl'

TRIGGER_KIND_CHOICES = (
	(VOICE, 'Make a call'),
	(SMS, 'Send a text or picture message'),
	(EMAIL, 'Send an email'),
	(CURL, 'Push data')
)

class Progress(db.Model):
	__tablename__ = 'progress'
	id = db.Column(db.Integer, primary_key=True)
	user = db.Column(EncryptedType(db.String, flask_secret_key))
	task = db.Column(db.String)
	time = db.Column(EncryptedType(db.DateTime, flask_secret_key))
	iterator = db.Column(db.Integer)
	parent_id = db.Column(db.Integer, db.ForeignKey('patients.id')) # this is the uniq_id?
	session_id = db.Column(db.String)
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
	description = db.Column(db.Text)
	head_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	head = db.relationship("Question",uselist=False, foreign_keys=[head_id])
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	read_public = db.Column(db.Boolean)
	edit_public = db.Column(db.Boolean)

	def push(survey, question):
		if survey.head==None:
			survey.head = question
			q = question
		else:
			q = survey.head
			while q.next_q!=None:
				q = q.next_q
			q.next_q = question
		return survey, question

	def questions(self):
		out = []
		q = self.head
		while q!=None:
			out.append(q)
			q = q.next_q
		return out

	def __str__(self):
		return '%s' % self.title
	
	def __init__(self, title=None, description=None):
		self.title = title
		self.description=description

class Question(db.Model):
	__tablename__ = 'question'
	
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	description = db.Column(db.Text)
	image = db.Column(db.String)
	kind = db.Column(ChoiceType(QUESTION_KIND_CHOICES))
	choices = db.Column(db.Text)
	survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'))
	triggers = db.relationship("Trigger", backref='question')
	next_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	next_q = db.relationship("Question", uselist=False, remote_side = [id], back_populates='prev_q')
	prev_q = db.relationship("Question", uselist=False, post_update=True)
	responses = db.relationship("QuestionResponse", backref='question')

	def __str__(self):
		return '%s' % self.body
	
	def __init__(self, body=None, description=None,
	             choices = None, image=None, kind=None, survey_id=None):
		self.body = body
		self.description = description
		self.choices = choices
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

class Comment(db.Model):
	__tablename__ = 'comment'
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(EncryptedType(db.String, flask_secret_key))
	time = db.Column(EncryptedType(db.DateTime, flask_secret_key))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'))

	def __init__(self, body, patient_id, user_id):
		self.body = body
		self.patient_id = patient_id
		self.user_id = user_id
		self.time = datetime.utcnow()

class QuestionResponse(db.Model):
	__tablename__ = 'question_response'
	id = db.Column(db.Integer, primary_key=True)
	response = db.Column(EncryptedType(db.String, flask_secret_key))
	time = db.Column(EncryptedType(db.DateTime, flask_secret_key))
	uniq_id = db.Column(db.Integer, db.ForeignKey('patients.id'))
	session_id = db.Column(EncryptedType(db.String, flask_secret_key))
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	survey_response_id = db.Column(db.Integer, db.ForeignKey('survey_response.id'))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	_question = db.relationship("Question", backref='_response')
	parent_session = db.relationship("SurveyResponse",backref="responses")

	def __str__(self):
		return '%s' % self.response
	
	def __init__(self, response=None, uniq_id=None, session_id=None, question_id=None, survey_response_id = None):
		self.response = response
		self.uniq_id = uniq_id
		self.session_id = session_id
		self.question_id = question_id
		self.survey_response_id = survey_response_id
		self.time = datetime.utcnow()

class SurveyResponse(db.Model):
	__tablename__ = 'survey_response'
	id = db.Column(db.Integer, primary_key=True)
	survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'))
	uniq_id = db.Column(db.Integer, db.ForeignKey('patients.id'))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	session_id = db.Column(EncryptedType(db.String, flask_secret_key))
	start_time = db.Column(EncryptedType(db.DateTime, flask_secret_key))
	end_time = db.Column(EncryptedType(db.DateTime, flask_secret_key))
	completed = db.Column(db.Boolean, default=False)
	survey = db.relationship("Survey", backref='response_sessions')

	def __str__(self):
		return '%s' % self.session_id
	
	def __init__(self, survey_id=None, uniq_id=None, session_id=None, user_id=None):
		self.survey_id = survey_id
		self.uniq_id = uniq_id
		self.session_id = session_id
		self.user_id = user_id
		self.start_time = datetime.utcnow()

	def complete(self):
		self.end_time = datetime.utcnow()
		self.completed = True

class Trigger(db.Model):
	__tablename__ = 'trigger'
	
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String)
	criteria = db.Column(db.String)
	kind = db.Column(ChoiceType(TRIGGER_KIND_CHOICES))
	recipients = db.Column(db.String)
	after_function = db.Column(db.String)
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
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
    admin = db.Column(db.Boolean, default=False)
    superadmin = db.Column(db.Boolean, default=False)
    google_token = db.Column(EncryptedType(db.String, flask_secret_key))
    authenticated = db.Column(db.Boolean, default=False)
    surveys = db.relationship("Survey", backref='user', lazy='dynamic')
    triggers = db.relationship("Trigger", backref='user', lazy='dynamic')
    responses = db.relationship("QuestionResponse", backref='user', lazy='dynamic')
    patients = db.relationship("Patient", backref='user', lazy='dynamic')
    comments = db.relationship("Comment", backref='user', lazy='dynamic')

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
	location = db.Column(EncryptedType(db.String, flask_secret_key))
	notes = db.Column(EncryptedType(db.String, flask_secret_key))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	responses = db.relationship("QuestionResponse", backref='patient', lazy='dynamic')
	progress = db.relationship("Progress", backref='patient', lazy='dynamic')