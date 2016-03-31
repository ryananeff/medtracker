from wtforms import *
from wtforms.ext.sqlalchemy.fields import QuerySelectField
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

class QuestionForm(Form):				
	'''GUI: question build form used in views'''
	body = TextField('Question', [validators.Length(min=5, max=255)])
	image = FileField('Upload an image')
	kind = SelectField('Type', choices=QUESTION_KIND_CHOICES)
	survey_id = SelectField("Survey", choices=[], coerce=int)
	
class TriggerForm(Form):				
	'''GUI: trigger build form used in views'''
	kind = SelectField('Type', choices=TRIGGER_KIND_CHOICES)
	questions = QuerySelectField("Attach to these questions", query_factory=Question.query.all, 
											get_pk=lambda a: a.id,
											get_label=lambda a: a.body)
	criteria = TextField('Match criteria', [validators.Length(min=1, max=50)])
	title = TextField('Message to send', [validators.Length(min=5, max=255)])
	after_function = TextField('Callback', [validators.Length(min=2, max=255)])

class QuestionView(MethodView):
	def get(self, question):
		class DynamicForm(Form): pass
		label, field = self.getField(question.kind)
		setattr(DynamicForm, label, field)
		d = DynamicForm() # Dont forget to instantiate your new form before rendering
		return d

	def getField(self, kind):
		label = [b for a,b in QUESTION_KIND_CHOICES if a==kind][0]
		if kind == "text":
			return label, TextField(label)
		if kind == "yes-no":
			return label, RadioField(label, choices=[(1,"Yes"), (0, "No")], coerce=int)
		if kind == "numeric":
			return label, SelectField(label, choices=[(a,str(a)) for a in range(1,11)], coerce=int)
		# can extend if clauses at every new fieldtype
    
