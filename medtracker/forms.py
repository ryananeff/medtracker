from wtforms import *
from flask_wtf import Form
from wtforms.ext.sqlalchemy.fields import *
from wtforms.fields.html5 import DateField, IntegerRangeField
from wtforms.validators import DataRequired
from wtforms.widgets.core import HTMLString, html_params, escape
from medtracker.models import *
from flask.views import MethodView
from medtracker.models import QUESTION_KIND_CHOICES, TRIGGER_KIND_CHOICES
import re, json

def select_multi_checkbox(field, ul_class='', **kwargs):
    kwargs.setdefault('type', 'checkbox')
    field_id = kwargs.pop('id', field.id)
    html = [u'<ul %s>' % html_params(id=field_id, class_=ul_class)]
    for value, label, checked in field.iter_choices():
        choice_id = u'%s-%s' % (field_id, value)
        options = dict(kwargs, name=field.name, value=value, id=choice_id)
        if checked:
            options['checked'] = 'checked'
        html.append(u'<li class="form-checkbox"><input %s /> ' % html_params(**options))
        html.append(u'<label for="%s">%s</label></li>' % (choice_id, label))
    html.append(u'</ul>')
    return HTMLString(u''.join(html))

def input_choices(field, ul_class='', **kwargs):
    field_id = kwargs.pop('id', field.id)
    html = []
    try:
    	choices = json.loads(field.data)
    except:
    	choices = {}
    for key, value in choices.items():
        html.append(u'<div class="btn-group"><input class="form-control" type="text" name="%s" value="%s"/><a href="#" class="delete" onclick="deleteParent(this);"><span class="glyphicon glyphicon-remove-circle"></span></a></div>' % (field_id,value))
    html.append(u'<div class="%s-container" %s></div>'%(field_id,html_params(id=field_id, class_=ul_class)))
    html.append(u'<button class="btn btn-primary add_form_field">Add Option &nbsp; <span class="add_form_field">+ </span></button></div>')
    return HTMLString(u''.join(html))

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
    description = TextAreaField('Description', [validators.Length(min=3)])

class QuestionForm(Form):				
	'''GUI: question build form used in views'''
	body = TextField('Question', [validators.Length(min=5, max=255)])
	description = TextAreaField('Description')
	image = FileField('Upload an image')
	kind = SelectField('Type', choices=QUESTION_KIND_CHOICES)
	choices = TextField('Options',widget=input_choices)
	survey_id = HiddenField("Survey")

class QuestionView(MethodView):
	def get(self, question):
		class DynamicForm(Form): pass
		label, field = self.getField(question)
		setattr(DynamicForm, label, field)
		d = DynamicForm() # Dont forget to instantiate your new form before rendering
		return d

	def getField(self, question):
		kind = question.kind
		qlabel = [b for a,b in QUESTION_KIND_CHOICES if a==kind][0]
		qtype = "response"
		if kind == "text":
			qlabel = "Write your response below."
			return qtype, TextField(qlabel,render_kw={"placeholder":"Your answer"})
		if kind == "yes-no":
			return qtype, RadioField(qlabel, choices=[(1,"Yes"), (0, "No")], coerce=int)
		if kind == "numeric":
			qlabel = "Drag the slider below."
			return qtype, IntegerRangeField(qlabel, [validators.NumberRange(min=1,max=9)], default=1)
		if kind == "select":
			qlabel = "Select one or more from the following:"
			try:
				choices = json.loads(question.choices,strict=False)
			except:
				choices = {}
			return qtype, SelectMultipleField(qlabel,choices = [(a,b) for a,b in choices.items()], coerce=int,widget=select_multi_checkbox)
		if kind == "radio":
			qlabel = "Choose from the following:"
			try:
				choices = json.loads(question.choices,strict=False)
			except:
				choices = {}
			return qtype, RadioField(qlabel, choices=[(a,b) for a,b in choices.items()], coerce=int)
		else: #if something is wrong
			qlabel = "Write your response below."
			return qtype, TextField(qlabel,render_kw={"placeholder":"Your answer"})
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
    username = StringField('E-mail', validators=[DataRequired()])
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
