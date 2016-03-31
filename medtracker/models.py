from medtracker.database import db
from medtracker.config import *
from sqlalchemy_utils import EncryptedType, ChoiceType

TEXT = 'text'
YES_NO = 'yes-no'
NUMERIC = 'numeric'
RADIO = 'radio'
SELECT = 'select'

QUESTION_KIND_CHOICES = (
	(TEXT, 'Type your answer below'),
	(YES_NO, 'Choose YES or NO'),
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

class Survey(db.Model):
	__tablename__ = 'survey'
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String)
	questions = db.relationship("Question", backref='survey', cascade="all, delete-orphan")

	def __str__(self):
		return '%s' % self.title
	
	def __init__(self, title=None):
		self.title = title

class Question(db.Model):
	__tablename__ = 'question'
	
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	image = db.Column(db.String)
	kind = db.Column(ChoiceType(QUESTION_KIND_CHOICES))
	survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'))
	trigger_id = db.Column(db.Integer, db.ForeignKey('trigger.id'))
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
	uniq_id = db.Column(EncryptedType(db.String, flask_secret_key))
	session_id = db.Column(EncryptedType(db.String, flask_secret_key))
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))

	def __str__(self):
		return '%s' % self.response

class Trigger(db.Model):
	__tablename__ = 'trigger'
	
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String)
	criteria = db.Column(db.String)
	kind = db.Column(ChoiceType(TRIGGER_KIND_CHOICES))
	questions = db.relationship("Question", backref='trigger')
	after_function = db.Column(db.String)

	def __str__(self):
		return '%s' % self.body
	
	def __init__(self, body=None, kind=None, criteria=None, af=None):
		self.title = body
		self.kind = kind
		self.criteria = criteria
		self.after_function = af


