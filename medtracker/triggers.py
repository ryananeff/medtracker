from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
import urllib

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
		resp.say("Hello, you have a new message from Suretify.")
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