from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
from medtracker.views import *
import sys
import urllib, re, random, string, requests, json
from flask_login import login_user, logout_user, current_user

def isfloat(value):
  try:
    float(value)
    return True
  except ValueError:
    return False

def randomword(length):
	'''generate a random string of whatever length, good for filenames'''
	return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def redirect_url():
    return request.args.get('next') or \
           request.referrer or \
           url_for('index')

def run_trigger(question, response, from_type = None, session_id = None, current_user = None):
	'''return: next_question, next_survey, exit, complete, message'''
	next_q = question.next_q
	if question.triggers:
		for trigger in question.triggers:
			#get conditions
			trigger_master_state = False
			trigger_comparators_next = None
			for ix,c in enumerate(trigger.conditions):
				trigger_state = False
				subject_response = QuestionResponse.query.filter_by(survey_response_id=response.survey_response_id,
				                                                    question_id=c.subject_id).first()
				c_value = c.condition_value.strip().lower()
				if subject_response != None:
					subject_response = subject_response._response.strip().lower() #get the response inputted for the trigger condition
				else:
					continue #there was no response for that trigger condition...
				sr_float = float(subject_response) if isfloat(subject_response) else subject_response
				cv_float = float(c_value) if isfloat(c_value) else c_value
				if c.comparator == "==":
					#subject_response must match condition value exactly (in lowercase, of course!)
					if subject_response==c_value:
						trigger_state = True
				elif c.comparator == "!=":
					if subject_response!=c_value:
						trigger_state = True
				elif c.comparator == "is in":
					if c_value in subject_response:
						trigger_state = True
				elif c.comparator == "is not in":
					if c_value not in subject_response:
						trigger_state = True
				elif c.comparator == "any":
					trigger_state = True
				elif c.comparator == "lt":
					try:
						if sr_float < cv_float:
							trigger_state=True
					except:
						continue
				elif c.comparator == "le":
					try:
						if sr_float <= cv_float:
							trigger_state=True
					except:
						continue
				elif c.comparator == "gt":
					try:
						if sr_float > cv_float:
							trigger_state=True
					except:
						continue
				elif c.comparator == "ge":
					try:
						if sr_float >= cv_float:
							trigger_state=True
					except:
						continue
				else:
					continue #we should never get to this line of code!
				if trigger_comparators_next != None:
					if trigger_comparators_next == "&":
						trigger_master_state = trigger_master_state&trigger_state
					elif trigger_comparators_next == "|":
						trigger_master_state = trigger_master_state|trigger_state
					elif trigger_comparators_next == ".":
						break
					else: #something went wrong
						break
				else:
					trigger_master_state = trigger_state
				trigger_comparators_next = c.next_comparator
				#end conditions
			#now we can branch if true or false
			trigger_type = None
			next_question = None
			message = None
			alerted = None
			if trigger_master_state: #if true
				trigger_type = trigger.yes_type
				next_question = trigger.dest_yes
				message = trigger.payload_yes
				alerted=trigger.alert_yes
			else: #if false
				trigger_type = trigger.no_type
				next_question = trigger.dest_no
				message = trigger.payload_no
				alerted=trigger.alert_no
			if trigger_type=="complete":
				'''return: next_question, next_survey, exit, complete, message'''
				return None, None, False, True, message
			elif trigger_type=="exit":
				'''return: next_question, next_survey, exit, complete, message'''
				return None, None, True, False, message
			elif trigger_type=="question":
				if next_question != None:
					return next_question.id,None,None,None,message
			elif trigger_type=="survey": 
				print("WARNING: survey redirect in trigger not implemented")
				continue #NOT IMPLEMENTED!
			elif trigger_type=="nothing":
				continue
	#no trigger active for question
	if next_q: #if more questions
		'''return: next_question, next_survey, exit, complete, message'''
		return next_q.id, None, False, False, None #do nothing if no trigger
	else: #exited without a completion record (completion must be explicit)
		'''return: next_question, next_survey, exit, complete, message'''
		return None, None, True, False, None

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
	formatted_recipients = []
	for r in recipients.split(";"):
		call = client.messages.create(body=message,
		to = r,
		from_ = twilio_number,
		)
		formatted_recipients.append(call.to)
	return formatted_recipients

@app.route("/test_sms/<int:survey_id>/<phone_number>", methods=["GET", "POST"])
@flask_login.login_required
def test_sms_survey(survey_id, phone_number, uniq_id = None):
	hello = "Hello! You have a new incoming survey from Suretify! Reply STOP to stop" #TODO: opt-in flow
	r_out = sms_trigger(hello, phone_number, None)
	if uniq_id == None:
		uniq_id = randomword(64)
	survey = Survey.query.get_or_404(survey_id)
	for r in r_out:
		task = Progress(
			user = r, 
			task = survey.id,
			parent_id = uniq_id)
		db_session.add(task)
	db_session.commit()
	msg = serve_sms_survey(task)
	recipients = sms_trigger(msg, phone_number, None)
	return "Task successfully queued."


@app.route("/sms", methods=["GET", "POST"])
def sms_gather_information():
	# TODO: this function needs to connect to a database that has a list of phone numbers, the current task that they are on, the iterator, and the initiator ID.
	# this will then allow us to handle survey answers and ask the next question
	from_phone = request.values.get("From", "+10000000000")
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

@app.route('/autocomplete/triggers', methods=["GET", "POST"])
@flask_login.login_required
def autocomplete_choices():
	surveys = current_user.surveys
	possible = []
	for survey in surveys:
		possible.append({"name": "survey." + str(survey.id), "content":survey.title})
		for ix, question in enumerate(survey._questions):
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
			print("No recipient defined for sending.")
			pass					
	elif method_type == 'sms':
		try:
			test_sms_survey(survey.id, patient.phone, uniq_id = patient.id)
			flash("Sent SMS to %s" % patient.phone)
		except:
			print("No recipient defined for sending.")
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
			print("Error in sending survey by email")
			pass
	return redirect(redirect_url())