from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
from medtracker.models import QUESTION_KIND_CHOICES, TRIGGER_KIND_CHOICES
from medtracker.views import save_response
import sys
import urllib, re

@app.route('/twilio/surveys/serve/<int:survey_id>', methods=['GET', 'POST'])
def serve_survey_twilio(survey_id):
	resp = twilio.twiml.Response()
	survey = Survey.query.get_or_404(survey_id)
	question_id = request.values.get("question", None)
	question_ids = [q.id for q in survey.questions]
	if len(question_ids) == 0:
			resp.message("Thanks for your time!")
			return str(resp)
	if question_id == None:
		question_id = question_ids[0]
	question_id = int(question_id)
	question = Question.query.get_or_404(question_id)
	resp.message(question.body)
	resp.message("("+[b for a,b in QUESTION_KIND_CHOICES if a==question.kind][0]+")")
	resp.redirect("/twilio/surveys/answer/" + str(survey.id) + "?question=" + str(question_id))
	return str(resp)

@app.route('/twilio/surveys/answer/<int:survey_id>', methods=['GET', 'POST'])
def answer_survey_twilio(survey_id):
	resp = twilio.twiml.Response()
	survey = Survey.query.get_or_404(survey_id)
	question_id = request.values.get("question", None)
	uniq_id = request.values.get("SmsSid", None)
	question_ids = [q.id for q in survey.questions]
	if len(question_ids) == 0:
			resp.message("Thanks for your time!")
			return str(resp)
	if question_id == None:
		question_id = question_ids[0]
	question_id = int(question_id)
	question = Question.query.get_or_404(question_id)
	curpos = question_ids.index(question_id)
	next_question = question_ids[curpos+1] if curpos+1 < len(question_ids) else None
	formdata = {}
	formdata["response"] = request.values.get("body", None)
	formdata["uniq_id"] = uniq_id
	if formdata["response"] != None:
		save_response(formdata, question_id)
	if next_question:
		resp.redirect("/twilio/surveys/serve/" + str(survey.id) + "?question=" + str(question_id))
	return str(resp)