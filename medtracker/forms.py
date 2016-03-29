from wtforms import *
from medtracker.models import QUESTION_KIND_CHOICES
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
	
    
