from wtforms import *
from flask_wtf import FlaskForm as Form
from wtforms.ext.sqlalchemy.fields import *
from wtforms.fields.html5 import DateField, IntegerRangeField, EmailField
from wtforms.validators import DataRequired, Length, EqualTo, InputRequired
from wtforms.widgets.core import HTMLString, html_params, escape, HiddenInput
from medtracker.models import *
from flask.views import MethodView
from medtracker.models import *
import re, json
from wtforms_alchemy import ModelForm, ModelFieldList
from wtforms.fields import FormField

class HiddenInteger(IntegerField):
    widget = HiddenInput()

def select_multi_checkbox(field, ul_class='response-multi', **kwargs):
    kwargs.setdefault('type', 'checkbox')
    field_id = kwargs.pop('id', field.id)
    html = [u'<ul %s>' % html_params(id=field_id, class_=ul_class)]
    for value, label, checked in field.iter_choices():
        choice_id = u'%s-%s' % (field_id, value)
        options = dict(kwargs, name=field.name, value=value, id=choice_id)
        if checked:
            options['checked'] = 'checked'
        html.append(u'<li class="form-checkbox">')
        html.append(u'<label for="%s">%s</label>' % (choice_id, label))
        html.append(u'<input %s /> ' % html_params(**options))
        html.append(u'</li>')
    html.append(u'</ul>')
    return HTMLString(u''.join(html))

def input_choices(field, ul_class='', **kwargs):
    field_id = kwargs.pop('id', field.id)
    html = [u'<label>Options</label>']
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
	body = TextField('Title', [validators.Length(min=5, max=255)])
	description = TextAreaField('Description')
	image_delete = BooleanField('Delete current image')
	image = FileField('Upload an image')
	kind = SelectField('Type', choices=QUESTION_KIND_CHOICES)
	choices = TextField('',widget=input_choices)
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
			return qtype, TextAreaField(qlabel,render_kw={"placeholder":"Your answer"})
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
			return qtype, TextAreaField(qlabel,render_kw={"placeholder":"Your answer"})
		# can extend if clauses at every new fieldtype

def possible_question():
	return Question.query

class TriggerConditionForm(ModelForm):
	class Meta:
		model = TriggerCondition
	#conditions
	subject = QuerySelectField("Subject", query_factory=possible_question,
		get_pk=lambda a: a.id, get_label=lambda a: a.body)
	comparator = SelectField("Comparator",choices=TRIGGER_COMPARATORS)
	condition_value = TextField("Condition value",render_kw={"placeholder":"value"})
	next_comparator = SelectField("Next",choices=TRIGGER_NEXT_COMPARATORS)    

class TriggerForm(ModelForm):
	class Meta:
		model = Trigger				
	'''GUI: trigger build form used in views'''
	question_id = HiddenInteger("Question id")
	#conditions
	conditions = ModelFieldList(FormField(TriggerConditionForm))
	#if true
	yes_type = SelectField('Type', choices=TRIGGER_KINDS)
	dest_yes = QuerySelectField("Destination", 
		get_pk=lambda a: a.id, get_label=lambda a: a.body, allow_blank=True)
	payload_yes = TextAreaField("Message")
	alert_yes = BooleanField("Alert")

	#if false
	no_type = SelectField('Type', choices=TRIGGER_KINDS)
	dest_no = QuerySelectField("Destination", 
		get_pk=lambda a: a.id, get_label=lambda a: a.body, allow_blank=True)
	payload_no = TextAreaField("Message")
	alert_no = BooleanField("Alert")

class UsernamePasswordForm(Form):
    username = StringField('E-mail', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class NewUserForm(Form):
	name = StringField('Full Name', validators=[DataRequired()])
	email = StringField('Email', validators=[DataRequired()])
	password = PasswordField('Password', validators=[DataRequired(),
	                         Length(min=8, max=40),
	                         EqualTo('confirm', message='Passwords must match')])
	confirm = PasswordField('Confirm Password')

class ChangePasswordForm(Form):
	current_password = PasswordField('Current Password', validators=[DataRequired()])
	new_password = PasswordField('New Password', validators=[DataRequired(),
	                         Length(min=8, max=40),
	                         EqualTo('confirm', message='New passwords must match')])
	confirm = PasswordField('Confirm New Password')

class ForgotPasswordForm(Form):
    email = EmailField(
        'Email', validators=[DataRequired()])

    # We don't validate the email address so we don't confirm to attackers
    # that an account with the given email exists.

class ResetPasswordForm(Form):
    email = EmailField(
        'Email', validators=[DataRequired()])
    new_password = PasswordField(
        'New password',
        validators=[
            InputRequired(),
            EqualTo('new_password2', 'Passwords must match.')
        ])
    new_password2 = PasswordField(
        'Confirm new password', validators=[InputRequired()])

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first() is None:
            raise ValidationError('Unknown email address.')

class PatientForm(Form):
	mrn = DisabledTextField('Patient Device ID')
	program = RadioField("What program are you in?", choices=PROGRAM_CHOICES)
	year = SelectField("What is your anticipated graduation date?",choices=[(i,i) for ix,i in enumerate(range(2020,2029))],coerce=int)
	location = RadioField("Where are you currently living?", choices=LOCATION_CHOICES)
	fullname = StringField('Name (optional)')
	age = StringField('Age (optional)')
	email = StringField('Email address (optional)')
	phone = StringField('Phone number (optional)')

class PatientEditForm(Form):
	mrn = HiddenField('Patient Device ID')
	program = RadioField("What program are you in?", choices=PROGRAM_CHOICES)
	year = SelectField("What is your anticipated graduation date?",choices=[(i,i) for ix,i in enumerate(range(2020,2029))],coerce=int)
	location = RadioField("Where are you currently living?", choices=LOCATION_CHOICES)
	fullname = StringField('Name (optional)')
	age = StringField('Age (optional)')
	email = StringField('Email address (optional)')
	phone = StringField('Phone number (optional)')