from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
import sys
import urllib, re, random, string, requests, json
from flask_login import login_user, logout_user, current_user


def run_trigger(question, response, current_user = None):
	if question.trigger:
		message = question.trigger.title
		split_message = re.split('(<.+?>)',message)
		for ix,i in enumerate(split_message):
			tag = re.findall('<(.+?)>',i) # look for tags we need to replace
			if tag != []:
				split_tag = tag[0].split(".")
				if len(split_tag) == 2: # db type is the resource type (question, trigger, callback, etc.), while the ID is actually the position in the survey
					db_type, db_id = split_tag
					db_subtype = None # subtype is if the element is multi-part (e.g. questions have elements attached)
				if len(split_tag) == 3:
					db_type, db_id, db_subtype = split_tag
				if db_type.lower() == 'question':
					result = QuestionResponse.query.filter_by(question_id=int(db_id), uniq_id=response.uniq_id).first()
					if result != None:
						split_message[ix] = result.response # this is the default subtype (response)
							#TODO: this needs to be fixed for things like yes or no questions or 1 to 10
							#        * maybe in the models??
					else:
						split_message[ix] = "" # when there's nothing there
				if db_type.lower() == 'survey':
					if current_user != None:
						surveys = Survey.query.filter_by(id=int(db_id), user_id=current_user.id).all()
						if len(surveys) != 0:
							survey = surveys[0]
						if question.trigger.kind == 'voice':
							for r in question.trigger.recipients.split(";"):
								test_voice_out(survey.id, r, uniq_id = response.uniq_id)
							return 0
						if question.trigger.kind == 'sms':
							for r in question.trigger.recipients.split(";"):
								test_sms_survey(survey.id, r, uniq_id = response.uniq_id)
							return 0
		message = "".join(split_message)
		if question.trigger.recipients == None:
			print "No valid recipients"
			return 2
		recipients = question.trigger.recipients
		callback = None
		if question.trigger.kind == 'voice':
			# TODO: needs to check if the recipient type is actually valid or else internal server error!
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

@app.route("/test_sms/<int:survey_id>/<phone_number>", methods=["GET", "POST"])
def test_sms_survey(survey_id, phone_number, uniq_id = None):
	if uniq_id == None:
		uniq_id = randomword(64)
	survey = Survey.query.get_or_404(survey_id)
	task = Progress(
		user = phone_number, 
		task = survey.id,
		parent_id = uniq_id)
	db_session.add(task)
	db_session.commit()
	msg = serve_sms_survey(task)
	hello = "Hello! You have a new incoming survey from Suretify!"
	sms_trigger(hello, phone_number, None)
	sms_trigger(msg, phone_number, None)
	return "Task successfully queued."


@app.route("/sms", methods=["GET", "POST"])
def sms_gather_information():
	# TODO: this function needs to connect to a database that has a list of phone numbers, the current task that they are on, the iterator, and the initiator ID.
	# this will then allow us to handle survey answers and ask the next question
	from_phone = request.values.get("From", "+10000000000")
	from_phone = from_phone[-10:]
	message = request.values.get("Body", None)
	current_tasks = Progress.query.filter_by(user=from_phone, complete=0).all()
	resp = twilio.twiml.Response()
	body = message.strip()
	if len(current_tasks) == 0:
		resp.message("You're already done responding!")
	else:
		last_task = current_tasks[0]
		# now we need to save the response if correct
		next_task, error = save_sms_survey(last_task, body)
		if error:
			resp.message(error)
		if next_task:
			msg = serve_sms_survey(next_task)
			resp.message(msg)
	return str(resp)

def serve_sms_survey(task):
	# TODO: this function will allow us to specify a survey as one of the callback functions and to ask it. Think a template is overkill here though.
	question, question_id, next_question, last_question = get_current_question(task)
	qlabel = [b for a,b in QUESTION_KIND_CHOICES if a==question.kind][0]
	return question.body + " (" + qlabel.lower() + ")"

def save_sms_survey(task, body):
	# TODO: this function will allow us to specify a survey as one of the callback functions and to ask it. Think a template is overkill here though.
	question, question_id, next_question, last_question = get_current_question(task)
	if question.kind != "text":
		body = body.lower()
		if question.kind == "numeric":
			if body not in [str(i) for i in range(1,10)]:
				return (task, "Please choose a number from 1 to 10.")
		if question.kind == "yes-no":
			if body not in ["yes", "y", "no", "n", "yes (y)", "no (n)"]:
				return (task, "Please respond with only YES (y) or NO (n)")
			else:
				if body in ["yes", "y"]:
					body = '1'
				else:
					body = '0'
	sys.stderr.write("body: " + body)
	save_basic_response(body, task.parent_id, question_id)
	if next_question == None:
		_ = increment_iterator(task)
		return (None, "Thank you for your responses. You're done!")
	new_task = increment_iterator(task)
	return (new_task, None)

def save_basic_response(message, uniq_id, question_id):
	_response = QuestionResponse(
		message,
		uniq_id,
		None,
		question_id
	)
	_response.user_id = None
	db_session.add(_response)
	db_session.commit()
	question = _response._question
	if _response.uniq_id != None:
		run_trigger(question, _response)
	return True

def get_current_question(task):
	survey = Survey.query.get_or_404(int(task.task))
	question_id = task.iterator
	question_ids = [q.id for q in survey.questions]
	if len(question_ids) == 0:
			return None, None, None, None
	if (question_id == None) | (question_id == ''): # if on first question
		question_id = question_ids[0]
	question_id = int(question_id)
	curpos = question_ids[question_id]
	question = Question.query.get_or_404(curpos)
	next_question = question_id+1 if question_id+1 < len(question_ids) else None
	last_question = question_id-1 if question_id-1 >= 0 else None
	sys.stderr.write("current: " + str(curpos) + " next: " + str(next_question) + " last: " + str(last_question))
	sys.stderr.flush()
	return question, curpos, next_question, last_question

def increment_iterator(task):
	question, question_id, next_question, last_question = get_current_question(task)
	if next_question == None:
		task.complete = 1
	task.iterator = next_question
	db_session.add(task)
	db_session.commit()
	return task

@app.route("/voice", methods=["GET", "POST"])
def voice_gather_information():
	# TODO: this function needs to connect to a database that has a list of phone numbers, the current task that they are on, the iterator, and the initiator ID.
	# this will then allow us to handle survey answers and ask the next question
	resp = twilio.twiml.Response()
	from_phone = request.values.get("To", "+10000000000")
	say_hello = int(request.values.get("hello", 0))
	from_phone = from_phone[-10:]
	message = request.values.get("RecordingUrl", None)
	digits = request.values.get("Digits", None)
	current_tasks = Progress.query.filter_by(user=from_phone, complete=0).all()
	if say_hello == 1:
		resp.say("Hello! You have a new incoming survey from Sure tiff eye!")
	if len(current_tasks) == 0:
		resp.say("You're already done responding!")
	else:
		last_task = current_tasks[0]
		# now we need to save the response if correct
		if say_hello == 0:
			next_task, error = save_voice_survey(last_task, message, digits)
			if error:
				resp.say(error)
		else:
			next_task = last_task
		if next_task:
			msg, record = serve_voice_survey(next_task)
			if record:
				resp.say(msg)
				resp.record(maxLength=300, action="/voice", method="POST", finishOnKey="#")
			else:
				with resp.gather(numDigits=1, action="/voice", method="POST") as g:
					resp.say(msg)
	return str(resp)

@app.route("/test_voice/<int:survey_id>/<phone_number>", methods=["GET", "POST"])
def test_voice_out(survey_id, phone_number, uniq_id = None):
	if uniq_id == None:
		uniq_id = randomword(64)
	survey = Survey.query.get_or_404(survey_id)
	task = Progress(
		user = phone_number, 
		task = survey.id,
		parent_id = uniq_id)
	db_session.add(task)
	db_session.commit()
	call = client.calls.create(url="https://suretify.co/voice?hello=1",
	  to = phone_number,
	  from_ = twilio_number)
	return "Task successfully queued."

def save_recording(recording_url):
	save_name = randomword(64) + ".mp3"
	base_dir = '/var/wsgiapps/suretify'
	save_dir = '/assets/audio/'
	with open(base_dir + save_dir + save_name, 'wb') as fp:
		response = requests.get(recording_url + ".mp3", auth=auth_combo, stream=True)
		for chunk in response.iter_content(chunk_size=2048):
			fp.write(chunk)
	return save_dir + save_name

def serve_voice_survey(task):
	# TODO: this function will allow us to specify a survey as one of the callback functions and to ask it. Think a template is overkill here though.
	question, question_id, next_question, last_question = get_current_question(task)
	qlabel = 'Please say your answer, followed by the pound key.'
	record = True
	if question.kind == 'numeric':
		qlabel = "Please rate the question from one to 9 on your keypad now."
		record = False
	if question.kind == 'yes-no':
		qlabel = "Please type 1 for yes and 2 for no on your keypad now."
		record = False
	return question.body + " " + qlabel, record

def save_voice_survey(task, message, digits):
	# TODO: this function will allow us to specify a survey as one of the callback functions and to ask it. Think a template is overkill here though.
	question, question_id, next_question, last_question = get_current_question(task)
	if question.kind != "text":
		if question.kind == "numeric":
			if digits not in [str(i) for i in range(1,9)]:
				return (task, "I'm sorry, I didn't get that. Please press a number from one to 9 on your keypad now.")
		if question.kind == "yes-no":
			if digits not in ['1','2']:
				return (task, "I'm sorry, I didn't get that. Please press 1 for yes and 2 for no on your keypad.")
			else:
				if digits == '1':
					digits = '0'
				else:
					digits="1"
		body = digits
	else:
		body = save_recording(message)
	save_basic_response(body, task.parent_id, question_id)
	if next_question == None:
		_ = increment_iterator(task)
		return (None, "Thank you for your responses. You're done!")
	new_task = increment_iterator(task)
	return (new_task, None)

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

def randomword(length):
	'''generate a random string of whatever length, good for filenames'''
	return ''.join(random.choice(string.lowercase) for i in range(length))

@app.route('/autocomplete/triggers', methods=["GET", "POST"])
@flask_login.login_required
def autocomplete_choices():
	surveys = current_user.surveys
	possible = []
	for survey in surveys:
		possible.append({"name": "survey." + str(survey.id), "content":survey.title})
		for ix, question in enumerate(survey.questions):
			possible.append({"name":"question." + str(question.id), "content":question.body})
	return json.dumps(possible)