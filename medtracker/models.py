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

TRIGGER_KIND_CHOICES = (
	(VOICE, 'Make a call'),
	(SMS, 'Send a text or picture message'),
	(EMAIL, 'Send an email'),
	(CURL, 'Push data')
)

NOTHING="nothing"
COMPLETE="complete"
EXIT="exit"
SURVEY="survey"

TRIGGER_KINDS = (
    (NOTHING,"Do nothing"),
	(COMPLETE, 'Complete survey'),
	(EXIT, 'Exit survey'),
	("question", 'Goto question'),
	(SURVEY, 'Goto survey')
)

EQUAL = "=="
NOTEQUAL = "!="
CONTAINS = "is in"
NOTCONTAIN = "is not in"
ANY = "any"

TRIGGER_COMPARATORS = (
    (EQUAL, "is equal to"),
    (NOTEQUAL, "is not equal to"),
    (CONTAINS, "contains"),
    (NOTCONTAIN, "does not contain"),
    ("lt","is less than"),
    ("gt","is greater than"),
    ("ge","is greater than or equal to"),
    ("le","is less than or equal to"),
    (ANY,"is any")
)

AND = "&"
OR = "|"

TRIGGER_NEXT_COMPARATORS = (
    (NOTHING,"."),
    (AND,"and"),
    (OR, "or")
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
	user = db.Column(db.Integer, db.ForeignKey('user.id'))
	task = db.Column(db.String)
	time = db.Column(db.DateTime)
	iterator = db.Column(db.Integer)
	parent_id = db.Column(db.Integer, db.ForeignKey('patients.id')) # this is the uniq_id?
	session_id = db.Column(db.String)
	complete = db.Column(db.Boolean)

	def __init__(self, **kwargs):
		self.time = datetime.datetime.now()
		self.complete = False
		super(Progress, self).__init__(**kwargs)

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

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class Comment(db.Model):
	__tablename__ = 'comment'
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(EncryptedType(db.String, flask_secret_key))
	time = db.Column(db.DateTime)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'))

	def __init__(self, **kwargs):
		super(Comment, self).__init__(**kwargs)
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
	
	def __init__(self,**kwargs):
		super(QuestionResponse, self).__init__(**kwargs)
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
	exited = db.Column(db.Boolean,default=False)
	completed = db.Column(db.Boolean, default=False)
	message = db.Column(db.Text)
	responses = db.relationship("QuestionResponse",backref="parent", lazy="dynamic",cascade="all,delete-orphan")

	def __str__(self):
		return '%s' % self.session_id
	
	def __init__(self,**kwargs):
		super(SurveyResponse, self).__init__(**kwargs)
		self.start_time = datetime.datetime.utcnow()

	def complete(self):
		self.end_time = datetime.datetime.utcnow()
		self.completed = True
		self.exited = False

	def exit(self):
		self.end_time = datetime.datetime.utcnow()
		self.exited = True
		self.completed = False
	
	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class Trigger(db.Model):
	__tablename__ = 'trigger'
	
	id = db.Column(db.Integer, primary_key=True)
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	conditions = db.relationship("TriggerCondition",backref="trigger",cascade="all,delete-orphan")
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	
	yes_type = db.Column(ChoiceType(TRIGGER_KINDS))
	dest_yes = db.Column(db.Integer, db.ForeignKey('question.id'))
	dest_yes_question = db.relationship("Question",foreign_keys=[dest_yes])
	payload_yes = db.Column(db.Text)
	alert_yes = db.Column(db.Boolean,default=False)

	no_type = db.Column(ChoiceType(TRIGGER_KINDS))
	dest_no = db.Column(db.Integer, db.ForeignKey('question.id'))
	dest_no_question = db.relationship("Question",foreign_keys=[dest_no])
	payload_no = db.Column(db.Text)
	alert_no = db.Column(db.Boolean,default=False)

	def __str__(self):
		return '%s' % self.body

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class TriggerCondition(db.Model):
	__tablename__= 'trigger_condition'

	id = db.Column(db.Integer, primary_key=True)
	trigger_id = db.Column(db.Integer, db.ForeignKey('trigger.id'))
	subject_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	question = db.relationship("Question")
	comparator = db.Column(ChoiceType(TRIGGER_COMPARATORS))
	condition_value = db.Column(db.String)
	next_comparator = db.Column(ChoiceType(TRIGGER_NEXT_COMPARATORS))

class Question(db.Model):
	__tablename__ = 'question'
	
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	description = db.Column(db.Text)
	image = db.Column(db.String)
	kind = db.Column(ChoiceType(QUESTION_KIND_CHOICES))
	choices = db.Column(db.Text)
	survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'))
	triggers = db.relationship("Trigger", foreign_keys=[Trigger.question_id],backref='question', cascade="all, delete-orphan")
	next_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	next_q = db.relationship("Question", uselist=False, remote_side = [id], back_populates='prev_q', post_update=True)
	prev_q = db.relationship("Question", uselist=False, post_update=True)
	responses = db.relationship("QuestionResponse", backref='question', cascade="all, delete-orphan")
	survey = db.relationship("Survey",foreign_keys=[survey_id],backref="_questions")

	def __str__(self):
		return '%s' % self.body

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class QuestionMeta(db.Model):
	__tablename__ = 'question_meta'
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
	
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
	reset_token = db.Column(EncryptedType(db.String, flask_secret_key))
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
	year = db.Column(db.Integer)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	surveys = db.relationship("SurveyResponse", backref='patient', lazy="dynamic", cascade="all, delete-orphan")
	responses = db.relationship("QuestionResponse", backref='patient', lazy="dynamic", cascade="all, delete-orphan")
	progress = db.relationship("Progress", backref='patient', lazy="dynamic", cascade="all, delete-orphan")
	creation_time = db.Column(db.DateTime, default=func.now())
	deactivate = db.Column(db.Boolean, default=False)

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}

class Device(db.Model):

	__tablename__= "devices"

	id = db.Column(db.Integer, primary_key=True)
	device_id = db.Column(db.String)
	creation_time = db.Column(db.DateTime, default=func.now())

	def to_dict(self):
		return {col.name: getattr(self, col.name) for col in self.__table__.columns}