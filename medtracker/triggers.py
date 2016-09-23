from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
from medtracker.views import *
import sys
import urllib, re, random, string, requests, json
from flask_login import login_user, logout_user, current_user

def redirect_url():
    return request.args.get('next') or \
           request.referrer or \
           url_for('index')

def run_trigger(question, response, session_id = None, current_user = None):
	if question.triggers:
		for trigger in question.triggers:
			message = trigger.title
			recipients = trigger.recipients
			split_message = re.split('(<.+?>)',message)
			split_recipients = re.split('(<.+?>)',recipients)
			criteria = trigger.criteria.lower().strip().encode()
			callback = Survey.query.filter_by(id=trigger.after_function, user_id=current_user.id).first()

			print "To evaluate: " + response.response
			# this code checks the criteria to see if it evaluates to true or false
			if criteria != 'any':
				print "Criteria is not any"
				if question.kind.code == "numeric":
					print "numeric code"
					try:
						if eval(response.response + " " + criteria) != True:
							print "Trigger did not match criteria."
							continue
					except:
						print "Can't determine if trigger matched criteria, failsafe stop."
						continue
				elif question.kind.code == "yes-no":
					print "yes-no code"
					try:
						yes_no = {'0':"no", '1':"yes"}
						if yes_no[response.response] != criteria:
							print "Trigger did not match criteria"
							continue
					except:
						print "Can't determine if trigger matched criteria, failsafe stop."
						continue
				else:
					print "other/text code"
					try:
						if eval(criteria + " " + response.response) != True:
							print "Trigger did not match criteria."
							continue
					except:
						print "Can't determine if trigger matched criteria, failsafe stop."
						continue

			# this code replaces the recipients field with the response
			for ix,i in enumerate(split_recipients):
				tag = re.findall('<(.+?)>',i) # look for tags we need to replace
				if tag != []:
					tag = tag[0].split("|")[1].strip() # so we can include descriptions
					split_tag = tag.split(".")
					if len(split_tag) == 2: # db type is the resource type (question, trigger, callback, etc.), while the ID is actually the position in the survey
						db_type, db_id = split_tag
						db_subtype = None # subtype is if the element is multi-part (e.g. questions have elements attached)
					if len(split_tag) == 3:
						db_type, db_id, db_subtype = split_tag
					if db_type.lower() == 'question':
						result = QuestionResponse.query.filter_by(question_id=int(db_id), uniq_id=response.uniq_id, session_id=session_id).first()
						if result != None:
							split_recipients[ix] = result.response.strip() # this is the default subtype (response)
								#TODO: this needs to be fixed for things like yes or no questions or 1 to 10
								#        * maybe in the models??
						else:
							split_recipients[ix] = "" # when there's nothing there
			recipients = "".join(split_recipients)

			# this code replaces the message field with the response
			for ix,i in enumerate(split_message):
				tag = re.findall('<(.+?)>',i) # look for tags we need to replace
				if tag != []:
					tag = tag[0].split("|")[1].strip() # so we can include descriptions
					split_tag = tag.split(".")
					if len(split_tag) == 2: # db type is the resource type (question, trigger, callback, etc.), while the ID is actually the position in the survey
						db_type, db_id = split_tag
						db_subtype = None # subtype is if the element is multi-part (e.g. questions have elements attached)
					if len(split_tag) == 3:
						db_type, db_id, db_subtype = split_tag
					if db_type.lower() == 'question':
						result = QuestionResponse.query.filter_by(question_id=int(db_id), uniq_id=response.uniq_id, session_id=session_id).first()
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
							if trigger.kind == 'voice':
								for r in recipients.split(";"):
									r = r.strip()
									test_voice_out(survey.id, r, uniq_id = response.uniq_id)
							if trigger.kind == 'sms':
								for r in recipients.split(";"):
									r = r.strip()
									test_sms_survey(survey.id, r, uniq_id = response.uniq_id)
							if trigger.kind == 'email':
								for r in recipients.split(";"):
									r = r.strip()
									url = "https://suretify.co" + url_for('start_survey', survey_id = callback.id) + "?u=%s" % response.uniq_id
									message = "Please complete the following survey at this link: %s" % url
									test_sms_survey(survey.id, r, uniq_id = response.uniq_id)
			message = "".join(split_message)
			if recipients == "":
				print "No valid recipients"
				continue
			if trigger.kind == 'voice':
				# TODO: needs to check if the recipient type is actually valid or else internal server error!
				phone_trigger(message, recipients, callback)
			elif trigger.kind == 'sms':
				sms_trigger(message, recipients, callback)
			elif trigger.kind == 'email':
				email_trigger(message, recipients, callback)
			elif trigger.kind == 'curl':
				url_trigger(message, recipients, callback)
			else:
				print "ERROR: Not a valid trigger type."
				continue
			print "Trigger sent successfully."

			if callback:
				if trigger.kind == 'voice':
					# TODO: needs to check if the recipient type is actually valid or else internal server error!
					try:
						recipients = Patient.query.get(response.uniq_id).phone
						test_voice_out(callback.id, recipients, uniq_id = response.uniq_id)
					except:
						print "No recipient defined for callback."
						pass					
				elif trigger.kind == 'sms':
					try:
						recipients = Patient.query.get(response.uniq_id).phone
						test_sms_survey(callback.id, recipients, uniq_id = response.uniq_id)
					except:
						print "No recipient defined for callback."
						pass
				elif trigger.kind == 'email':
					#TODO - need to generate the URL to send out
					try:
						url = "https://suretify.co" + url_for('start_survey', survey_id = callback.id) + "?u=%s" % response.uniq_id
						message = "Please complete the following survey at this link: %s" % url
						recipients = Patient.query.get(response.uniq_id).email
						task = Progress(
							user = recipients, 
							task = callback.id,
							parent_id = response.uniq_id)
						db_session.add(task)
						db_session.commit()
						email_trigger(message, recipients, callback)
					except:
						print "Error in sending email callback"
						pass
				elif trigger.kind == 'curl':
					# TODO - need to generate the URL to send out
					#url_trigger(message, recipients, callback)
					pass
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
		resp.say("Hello, you have a new message from Sure tiff fy, but at this time we are having trouble playing it. Goodbye.")
	return str(resp)

def sms_trigger(message, recipients, callback=None):
	for r in recipients.split(";"):
		call = client.messages.create(body=message,
		to = r,
		from_ = twilio_number,
		)
	return None

@app.route("/test_sms/<int:survey_id>/<phone_number>", methods=["GET", "POST"])
@flask_login.login_required
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
	hello = "Hello! You have a new incoming survey from Suretify! Reply STOP to stop" #TODO: opt-in flow
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
			if body not in [str(i) for i in range(1,11)]:
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
	save_basic_response(body, task.parent_id, question_id, session_id = task.session_id)
	if next_question == None:
		_ = increment_iterator(task)
		return (None, "Thank you for your responses. You're done!")
	new_task = increment_iterator(task)
	return (new_task, None)

def save_basic_response(message, uniq_id, question_id, session_id = None):
	_response = QuestionResponse(
		message,
		uniq_id,
		session_id,
		question_id
	)
	_response.user_id = Patient.query.get(uniq_id).user_id
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
@flask_login.login_required
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
	save_basic_response(body, task.parent_id, question_id, session_id=task.session_id)
	if next_question == None:
		_ = increment_iterator(task)
		return (None, "Thank you for your responses. You're done!")
	new_task = increment_iterator(task)
	return (new_task, None)

def email_trigger(message, recipients, callback=None):
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

@app.route("/prod/<prod_type>/<int:patient_id>", methods=["GET", "POST"])
@flask_login.login_required
def prod_patient(prod_type, patient_id):
	# TODO: this function needs to connect to a database that has a list of phone numbers, the current task that they are on, the iterator, and the initiator ID.
	# this will then allow us to handle survey answers and ask the next question
	patient = Patient.query.get_or_404(patient_id)
	current_tasks = Progress.query.filter_by(parent_id=patient.id, complete=0).all()
	if len(current_tasks) == 0:
		return "No incomplete tasks found - all tasks complete.", 404
	else:
		last_task = current_tasks[0]
		recipients = last_task.user
		# now we need to save the response if correct
		if prod_type == "sms":
			resp = twilio.twiml.Response()
			msg = serve_sms_survey(last_task)
			try:
				sms_trigger(msg, last_task.user, None)
			except:
				return "Error sending SMS prod.", 500
		elif prod_type == "voice":
			call = client.calls.create(url="https://suretify.co/triggers/voice?say_hello=1",
			to = recipients,
			from_ = twilio_number,
			)
		elif prod_type == "email":
			questions = [i.id for i in Survey.query.get_or_404(last_task.task).questions]
			url = "https://suretify.co/surveys/serve/%s?question=%s&u=%s" % last_task.task, questions[last_task.iterator], last_task.parent_id
			message = "Please continue the following survey at this link: %s" % url
			email_trigger(message, recipients, None)
		elif prod_type == "clear":
			# mark all complete
			for i in current_tasks:
				i.complete = 1
				db_session.add(i)
			db_session.commit()
		else:
			return "Couldn't find prod type, not implemented.", 400
	return redirect(redirect_url())

@app.route("/send_survey/<method_type>/<int:patient_id>/<int:survey_id>", methods=["GET", "POST"])
@flask_login.login_required
def send_survey(method_type,patient_id, survey_id):
	survey = Survey.query.filter_by(id=survey_id, user_id=current_user.id).first_or_404()
	patient = Patient.query.filter_by(id=patient_id, user_id=current_user.id).first_or_404()
	if method_type == 'voice':
		# TODO: needs to check if the recipient type is actually valid or else internal server error!
		try:
			test_voice_out(survey.id, patient.phone, uniq_id = patient.id)
			flash("Calling %s" % patient.phone)
		except:
			print "No recipient definedfor sending."
			pass					
	elif method_type == 'sms':
		try:
			test_sms_survey(survey.id, patient.phone, uniq_id = patient.id)
			flash("Sent SMS to %s" % patient.phone)
		except:
			print "No recipient defined for sending."
			pass
	elif method_type == 'email':
		#TODO - need to generate the URL to send out
		try:
			url = "https://suretify.co" + url_for('start_survey', survey_id = survey.id) + "?u=%s" % patient.id
			message = "Please complete the following survey at this link: %s" % url
			task = Progress(
				user = patient.email, 
				task = survey.id,
				parent_id = patient.id)
			db_session.add(task)
			db_session.commit()
			email_trigger(message, patient.email, None)
			flash("Sent email to %s" % patient.email)
		except:
			print "Error in sending survey by email"
			pass
	return redirect(redirect_url())