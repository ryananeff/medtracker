from medtracker import *
from medtracker.database import db
from medtracker.config import *
from sqlalchemy_utils import EncryptedType, ChoiceType
from passlib.apps import custom_app_context as pwd_context
from sqlalchemy.sql import func

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
COMPLETE="complete"
EXIT="exit"
QUESTION="question",
SURVEY="survey"
NOTHING="nothing"

TRIGGER_KIND_CHOICES = (
	(VOICE, 'Make a call'),
	(SMS, 'Send a text or picture message'),
	(EMAIL, 'Send an email'),
	(CURL, 'Push data')
)

TRIGGER_KINDS = (
    (NOTHING,"Do nothing"),
	(COMPLETE, 'Complete survey'),
	(EXIT, 'Exit survey'),
	(QUESTION, 'Goto question'),
	(SURVEY, 'Goto survey')
)

LOCATION_CHOICES = [
		("student_housing", "Student housing (e.g. Aron Hall)"),
		("mount_sinai", "Mount Sinai-owned properties"),
		("other_nyc", "Other housing (inside NYC)"),
		("other_outside", "Other housing (other locations)")
	]

PROGRAM_CHOICES = [
		("MD", "MD"),
		("PhD", "PhD"),
		("dual", "Dual degree programs (e.g. MD/PhD)"),
		("master", "Master's (e.g. MS, MPH)"),
		("other", "My program isn't listed here")
	]

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

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}
	
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
	responses = db.relationship("SurveyResponse", backref='survey', cascade="all, delete-orphan",lazy="dynamic")

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

	def remove(survey,question):
		qlist = survey.questions()
		edited = []
		for ix,q in enumerate(qlist):
			if q.id==question.id:
				if ix==0:
					if ix != (len(qlist)-1):
						survey.head = qlist[ix+1]
					else:
						survey.head = None
					edited.append(survey)
				else:
					if ix != (len(qlist)-1):
						qlist[ix-1].next_q = qlist[ix+1]
						edited.extend([qlist[ix-1],qlist[ix+1]])
					else:
						qlist[ix-1].next_q = None
						edited.append(qlist[ix-1])
				break
		return edited

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

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

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
	next_q = db.relationship("Question", uselist=False, remote_side = [id], back_populates='prev_q', post_update=True)
	prev_q = db.relationship("Question", uselist=False, post_update=True)
	responses = db.relationship("QuestionResponse", backref='question', cascade="all, delete-orphan")
	survey = db.relationship("Survey",foreign_keys=[survey_id],backref="_questions")

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

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class QuestionMeta(db.Model):
	__tablename__ = 'question_meta'
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	
	def __init__(self, body=None, question=None):
		self.body = body
		self.question_id = question_id
	
	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class Comment(db.Model):
	__tablename__ = 'comment'
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	time = db.Column(db.DateTime)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'))

	def __init__(self, body, patient_id, user_id):
		self.body = body
		self.patient_id = patient_id
		self.user_id = user_id
		self.time = datetime.datetime.utcnow()

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class QuestionResponse(db.Model):
	__tablename__ = 'question_response'
	id = db.Column(db.Integer, primary_key=True)
	_response = db.Column(db.String)
	time = db.Column(db.DateTime)
	uniq_id = db.Column(db.Integer, db.ForeignKey('patients.id'))
	session_id = db.Column(db.String)
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	survey_response_id = db.Column(db.Integer, db.ForeignKey('survey_response.id'))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	_question = db.relationship("Question", backref='_response')

	def __str__(self):
		return '%s' % self.response

	@property
	def response(self):
		return [x for x in self._response.split(';')]

	@response.setter
	def response(self,value):
		if type(value)!=list:
			value = [value]
		self._response = ";".join([str(a) for a in value])
	
	def __init__(self, response=None, uniq_id=None, session_id=None, question_id=None, survey_response_id = None):
		self.response = response
		self.uniq_id = uniq_id
		self.session_id = session_id
		self.question_id = question_id
		self.survey_response_id = survey_response_id
		self.time = datetime.datetime.utcnow()

	def to_dict(self):
		outdict = {col.name: getattr(self, col.name) for col in self.__table__.columns}
		outdict["response"] = self._response
		outdict["question_title"] = self._question.body
		outdict["question_choices"] = self._question.choices
		outdict["question_type"] = self._question.kind.code
		outdict["survey_title"] = self._question.survey.title
		outdict["survey_id"] = self._question.survey.id
		return outdict

class SurveyResponse(db.Model):
	__tablename__ = 'survey_response'
	id = db.Column(db.Integer, primary_key=True)
	survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'))
	uniq_id = db.Column(db.Integer, db.ForeignKey('patients.id'))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	session_id = db.Column(db.String)
	start_time = db.Column(db.DateTime)
	end_time = db.Column(db.DateTime)
	completed = db.Column(db.Boolean, default=False)
	responses = db.relationship("QuestionResponse",backref="parent",lazy="dynamic", cascade="all,delete-orphan")

	def __str__(self):
		return '%s' % self.session_id
	
	def __init__(self, survey_id=None, uniq_id=None, session_id=None, user_id=None):
		self.survey_id = survey_id
		self.uniq_id = uniq_id
		self.session_id = session_id
		self.user_id = user_id
		self.start_time = datetime.datetime.utcnow()

	def complete(self):
		self.end_time = datetime.datetime.utcnow()
		self.completed = True
	
	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

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

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

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
	comments = db.relationship("Comment", backref='user', lazy='dynamic',cascade="all, delete-orphan")

	def is_active(self):
	    return self.active

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

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class Patient(db.Model):
	'''A patient record capable of taking surveys'''
	__tablename__= "patients"

	id = db.Column(db.Integer, primary_key=True)
	mrn = db.Column(EncryptedType(db.String, flask_secret_key))
	fullname = db.Column(EncryptedType(db.String, flask_secret_key))
	age = db.Column(EncryptedType(db.String, flask_secret_key))
	phone = db.Column(EncryptedType(db.String, flask_secret_key))
	email = db.Column(EncryptedType(db.String, flask_secret_key))
	location = db.Column(ChoiceType(LOCATION_CHOICES))
	program = db.Column(ChoiceType(PROGRAM_CHOICES))
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	surveys = db.relationship("SurveyResponse", backref='patient', lazy="dynamic", cascade="all, delete-orphan")
	responses = db.relationship("QuestionResponse", backref='patient', lazy='dynamic', cascade="all, delete-orphan")
	progress = db.relationship("Progress", backref='patient', lazy='dynamic', cascade="all, delete-orphan")
	creation_time = db.Column(db.DateTime, default=func.now())

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class Device(db.Model):

	__tablename__= "devices"

	id = db.Column(db.Integer, primary_key=True)
	device_id = db.Column(EncryptedType(db.String, flask_secret_key))
	creation_time = db.Column(db.DateTime, default=func.now())

	def __init__(self,device_id):
		self.device_id = device_id

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}