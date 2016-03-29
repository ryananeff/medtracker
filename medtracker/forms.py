from wtforms import Form, TextField, validators, FileField
import re

class DisabledTextField(TextField):
  def __call__(self, *args, **kwargs):
    kwargs.setdefault('disabled', True)
    return super(DisabledTextField, self).__call__(*args, **kwargs)

class SurveyForm(Form):				
    '''GUI: survey build form used in views'''
    title = TextField('Title', [validators.Length(min=3, max=255)])
