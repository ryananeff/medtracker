from medtracker.database import db
from sqlalchemy_utils import EncryptedType, ChoiceType

class Survey(db.Model):
	__tablename__ = 'survey'
	id = db.Column(db.Integer, primary_key=True)
	title = db.Column(db.String)

	def __str__(self):
		return '%s' % self.title

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
	survey = db.Column(db.relationship("survey"))

	def __str__(self):
		return '%s' % self.body


class QuestionResponse(db.Model):
	__tablename__ = 'question_response'
	id = db.Column(db.Integer, primary_key=True)
	response = db.Column(EncryptedType(db.String, flask_secret_key))
	uniq_id = db.Column(EncryptedType(db.String, flask_secret_key))
	session_id = db.Column(EncryptedType(db.String, flask_secret_key))
	question = db.Column(db.relationship("question"))

	def __str__(self):
		return '%s' % self.response
