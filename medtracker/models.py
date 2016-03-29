from medtracker.database import db
from medtracker.config import *
from sqlalchemy_utils import EncryptedType, ChoiceType

class Survey(db.Model):
	__tablename__ = 'survey'
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String)

	def __str__(self):
		return '%s' % self.title
	
	def __init__(self, title=title):
		self.title = title

class Question(db.Model):
	__tablename__ = 'question'
	TEXT = 'text'
	YES_NO = 'yes-no'
	NUMERIC = 'numeric'

	QUESTION_KIND_CHOICES = (
		(TEXT, 'Type your answer below'),
		(YES_NO, 'Choose one'),
		(NUMERIC, 'Choose one')
	)
	id = db.Column(db.Integer, primary_key=True)
	body = db.Column(db.String)
	image = db.Column(db.String)
	kind = db.Column(ChoiceType(QUESTION_KIND_CHOICES))
	survey = db.Column(db.Integer, db.ForeignKey('survey.id'))
	survey_obj = db.relationship("Survey", backref=db.backref('questions', lazy='dynamic'))

	def __str__(self):
		return '%s' % self.body


class QuestionResponse(db.Model):
	__tablename__ = 'question_response'
	id = db.Column(db.Integer, primary_key=True)
	response = db.Column(EncryptedType(db.String, flask_secret_key))
	uniq_id = db.Column(EncryptedType(db.String, flask_secret_key))
	session_id = db.Column(EncryptedType(db.String, flask_secret_key))
	question = db.Column(db.Integer, db.ForeignKey('question.id'))
	question_obj = db.relationship("Question", backref=db.backref('responses', lazy='dynamic'))

	def __str__(self):
		return '%s' % self.response
