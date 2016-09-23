from wtforms import *
from flask_wtf import Form
from wtforms.ext.sqlalchemy.fields import *
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired
from medtracker.models import *
from flask.views import MethodView
from medtracker.models import QUESTION_KIND_CHOICES, TRIGGER_KIND_CHOICES
import re

class DisabledTextField(TextField):
  def __call__(self, *args, **kwargs):
    kwargs.setdefault('disabled', True)
    return super(DisabledTextField, self).__call__(*args, **kwargs)

class DisabledSelectField(SelectField):
  def __call__(self, *args, **kwargs):
    kwargs.setdefault('disabled', True)
    return super(DisabledSelectField, self).__call__(*args, **kwargs)

class SurveyForm(Form):				
    '''GUI: survey build form used in views'''
    title = TextField('Title', [validators.Length(min=3, max=255)])
    description = TextAreaField('Description', [validators.Length(min=3, max=255)])

class QuestionForm(Form):				
	'''GUI: question build form used in views'''
	body = TextField('Question', [validators.Length(min=5, max=255)])
	image = FileField('Upload an image')
	kind = SelectField('Type', choices=QUESTION_KIND_CHOICES)
	survey_id = SelectField("Survey", choices=[], coerce=int)

class QuestionView(MethodView):
	def get(self, question):
		class DynamicForm(Form): pass
		label, field = self.getField(question.kind)
		setattr(DynamicForm, label, field)
		d = DynamicForm() # Dont forget to instantiate your new form before rendering
		return d

	def getField(self, kind):
		qlabel = [b for a,b in QUESTION_KIND_CHOICES if a==kind][0]
		qtype = "response"
		if kind == "text":
			return qtype, TextField(qlabel)
		if kind == "yes-no":
			return qtype, RadioField(qlabel, choices=[(1,"Yes"), (0, "No")], coerce=int)
		if kind == "numeric":
			return qtype, SelectField(qlabel, choices=[(a,str(a)) for a in range(1,11)], coerce=int)
		else:
			qlabel = "Select from the following"
			return qtype, TextField(qlabel)
		# can extend if clauses at every new fieldtype
    
class TriggerForm(Form):				
	'''GUI: trigger build form used in views'''
	kind = SelectField('Type', choices=TRIGGER_KIND_CHOICES)
	criteria = TextField('Match criteria', [validators.Length(min=1, max=50)])
	title = TextAreaField('Message to send', [validators.Length(min=0, max=255)])
	recipients = TextField('Recipients', [validators.Length(min=4, max=255)])
	after_function = QuerySelectField("Callback", 
		get_pk=lambda a: a.id, get_label=lambda a: a.title, allow_blank=True)
	question_id = QuerySelectField("Attach to this question", 
		get_pk=lambda a: a.id, get_label=lambda a: a.body)

class UsernamePasswordForm(Form):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class NewUserForm(Form):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    username = StringField('Username', validators=[DataRequired()])
    name = StringField('Full Name', validators=[DataRequired()])

class PatientForm(Form):
	mrn = DisabledTextField('MRN')
	fullname = StringField('Full Name', validators=[validators.Length(min=4, max=255)])
	dob = DateField('Date of Birth', validators=[DataRequired()], format="%Y-%m-%d")
	phone = StringField('Phone number', validators=[DataRequired()])
	email = StringField('Email address', validators=[validators.Email()])
	notes = StringField('Additional Notes')