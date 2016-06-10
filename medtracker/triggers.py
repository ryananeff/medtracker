from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
import sys
import urllib, re

def run_trigger(question, response):
	sys.stderr.write("triggering")
	if question.trigger:
		message = question.trigger.title
		split_message = re.split('(<.+?>)',message)
		for ix,i in enumerate(split_message):
			tag = re.findall('<(.+?)>',i)
			if tag != []:
				split_tag = tag[0].split(".")
				if len(split_tag) == 2:
					db_type, db_id = split_tag
					db_subtype = None
				if len(split_tag) == 3:
					db_type, db_id, db_subtype = split_tag
				if db_type.lower() == 'question':
					question_ids = [q.id for q in response.question.survey.questions]
					result = QuestionResponse.query.filter_by(question_id=question_ids[int(db_id)-1], uniq_id=response.uniq_id).first() if question_ids != [] else None
					if result != None:
						split_message[ix] = result.response
					else:
						split_message[ix] = ""
		message = "".join(split_message)
		if question.trigger.recipients == None:
			print "No valid recipients"
			return 2
		recipients = question.trigger.recipients
		callback = None
		if question.trigger.kind == 'voice':
			phone_trigger(message, recipients, callback)
		elif question.trigger.kind == 'sms':
			sms_trigger(message, recipients, callback)
		elif question.trigger.kind == 'email':
			email_trigger(message, recipients, callback)
		elif question.trigger.kind == 'curl':
			url_trigger(message, recipients, callback)
		else:
			print "ERROR: Not a valid trigger type."
			return 1
		print "Trigger sent successfully."
		return 0

def phone_trigger(message, recipients, callback=None):
	'''send a trigger message at a certain time'''
	for r in recipients.split(";"):
		call = client.calls.create(url="https://suretify.co/triggers/phone?m=" + urllib.quote(message),
		to = r,
		from_ = twilio_number,
		)
	return None

@app.route("/triggers/phone", methods=["GET", "POST"])
def read_phone_trigger_message():
	resp = twilio.twiml.Response()
	message = request.values.get("m", None)
	if message:
		resp.say("Hello, you have a new message from Sure tiff fy.")
		resp.pause(length=1)
		resp.say(message)
	else:
		resp.say("Hello, you have a new message from Suretify, but at this time we are having trouble playing it. Goodbye.")
	return str(resp)

def sms_trigger(message, recipients, callback):
	for r in recipients.split(";"):
		call = client.messages.create(body=message,
		to = r,
		from_ = twilio_number,
		)
	return None

def email_trigger(message, recipients, callback):
	for r in recipients.split(";"):
		subject = "Request for information from Suretify"
		with app.app_context():
			html = render_template(
	            'trigger_email.html',
	            body=message)
			send_email(r, subject, html)
	return None

def url_trigger(message, recipients, callback):
	for r in recipients.split(";"):
		requests.get(r % (urllib.quote(message)))
	return None