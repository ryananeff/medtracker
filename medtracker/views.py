import medtracker
from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
from medtracker.triggers import *
from werkzeug.exceptions import InternalServerError
from flask_mail import Mail, Message

import matplotlib as mpl
import matplotlib.cm as cm
from plotly import offline
import pandas as pd
import numpy as np
import datetime
import plotly
import plotly.graph_objects as go
import ast
from collections import defaultdict
from datetime import timezone
import time
from sqlalchemy import or_ 
from sqlalchemy import func, cast, Date

from pytz import timezone as pytztimezone
tz = pytztimezone('EST')

image_staticdir = 'assets/uploads/'
base_dir = os.path.realpath(os.path.dirname(medtracker.__file__)+"/../")

@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html',message=e), 404

@app.errorhandler(401)
def page_unauth(e):
    # note that we set the 401 status explicitly
    return render_template('401.html',message=e), 401

@app.errorhandler(403)
def page_unauth_forbidden(e):
    # note that we set the 401 status explicitly
    return render_template('401.html',message=e), 403

@app.errorhandler(405)
def page_badmethod(e):
    # note that we set the 405 status explicitly
    return render_template('405.html',message=e), 405

@app.errorhandler(500)
def handle_500(e):
    original = getattr(e, "original_exception", None)

    if original is None:
        # direct 500 error, such as abort(500)
        return render_template("500.html"), 500

    # wrapped unhandled error
    return render_template("500.html", message=original), 500

def randomword(length):
	'''generate a random string of whatever length, good for filenames'''
	return ''.join(random.choice('23456789ABCDEFGHIJKLMNPQRSTUVWXYZ') for i in range(length))

def fmt_id(str):
	out = ""
	for ix,i in enumerate(str):
		out += i
		if (ix % 4 == 3)*(ix!=len(str)-1):
			out += "-"
	return out

@app.context_processor
def utility_processor():
	return dict(fmt_id=fmt_id)

#### session_persistance functions
@app.before_request
def detect_user_session():
	g.patient = None
	g.patient_ident = None
	patient_ident_req = request.cookies.get('patient_ident')
	#check if we generated the patient_ident (ensure it wasn't randomly made up)
	g.device = Device.query.filter_by(device_id=patient_ident_req).first()

	if (patient_ident_req is None)|(g.device is None):

		g.patient_ident = randomword(16)

		# when the response exists, set a cookie with the language
		@after_this_request
		def remember_pt_id(response):
			response.set_cookie('patient_ident', g.patient_ident, max_age=datetime.timedelta(weeks=52))
			device = Device(device_id = g.patient_ident)
			db.session.add(device)
			db.session.commit()
			g.device = device
			return response
	else:
		g.patient_ident = g.device.device_id
		g.patient = Patient.query.filter_by(mrn=g.patient_ident).first()
	if current_user.is_authenticated:
		current_user.surveys = Survey.query
		current_user.patients = Patient.query

#### logins

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view =  "login"
login_manager.session_protection = "strong"

@login_manager.user_loader
def user_loader(user_id):				# used by Flask internally to load logged-in user from session
	user = User.query.get(user_id)
	if user.active == False:
		user = None
	return user

@login_manager.unauthorized_handler
@app.route("/login", methods=["GET", "POST"])
def login():					# not logged-in callback
	form = UsernamePasswordForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.username.data.lower()).first()
		if user == None:
			flash("Error: '" + form.username.data + "'")
			return render_template('form_login.html', form=form, action="Please log in", data_type="")
		if user.active == False:
			msg = Markup('Your account is currently deactivated until an administrator activates it.')
			flash(msg)
			return redirect(url_for('login'))
		elif user.verify_password(form.password.data):
			login_user(user, remember=True, duration = datetime.timedelta(weeks=52))
			return redirect(url_for('index'))
		else:
			return redirect(url_for('login'))
	return render_template('form_login.html', form=form, action="Please log in", data_type="")

@app.route('/logout')
def signout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/signup', methods=["GET", "POST"])
def signup():
	form = NewUserForm()
	if form.validate_on_submit():
		olduser = User.query.filter_by(email=form.email.data.lower()).first()
		if olduser:
			flash("Already registered with that address. Log in or reset password.")
			return redirect(url_for("login"))
		user = User(
		    email = form.email.data.lower(),
		    name = form.name.data,
		)
		user.hash_password(form.password.data)
		db.session.add(user)
		db.session.commit()

		flash("Successfully registered. Your account is currently inactive. You must wait for another current admin to grant your admin access.")
		return redirect(url_for("login"))

	return render_template('form_signup.html', form=form, action="Sign up for ISMMS Health Check", data_type="")

@app.route('/change-password', methods=['GET', 'POST'])
@flask_login.login_required
def change_password():
	form = ChangePasswordForm()
	if form.validate_on_submit():
		user = current_user
		if user.verify_password(form.current_password.data):
		    user.hash_password(form.new_password.data)
		    db.session.add(user)
		    db.session.commit()
		    flash('Your password was successfully changed.')
		    if request.referrer == None:
		    	return redirect(url_for('serve_survey_index'))
		    else:
		    	return redirect(request.referrer)
		form.current_password.errors.append('Invalid password.')
	return render_template('change_password.html', form=form, action="Change password", data_type="")

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        flash('You are already logged in.')
        return redirect(url_for('index'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            send_reset_email(user = user)
        flash("Password reset requested.")
        return redirect(url_for('index'))
    return render_template('forgot_password.html', form=form)

@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password_with_token(token):
    if current_user.is_authenticated:
        flash('You are already logged in.')
        return redirect(url_for("index"))
    user = User.query.filter_by(reset_token = token).first()
    if user is None:
        return abort(404)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.hash_password(form.new_password.data)
        user.reset_token = None
        login_user(user,remember=True, duration = datetime.timedelta(weeks=52))
        db.session.add(user)
        db.session.commit()
        flash('Your password was successfully changed.')
        return redirect(url_for('serve_survey_index'))
    return render_template('reset_password.html', form=form)

def send_reset_email(user, app=app):
	'''send an email to reset the user's password'''
	# look for configuration variables in params.conf file...
	msg = Message(sender=config.mail_server_sender)
	msg.subject = "ISMMS Student Health Check Password Reset Request"
	msg.sender  = config.mail_server_sender
	msg.recipients = [user.email]
	user.reset_token = randomword(24)
	with app.app_context():
		msg.html = render_template('email.html', token = user.reset_token)
		msg.body = render_template('email.txt', token = user.reset_token)
	mail.send(msg)
	db.session.add(user)
	db.session.commit()
	return None

def check_patient_identified(patient):
	# Check that the person has filled out all the required fields
	# Required: full name, email, life number
	if patient==None:
		return False
	not_failed = True
	if (patient.fullname==None)|(patient.lifenumber==None)|(patient.email==None):
		return False
	if (len(patient.fullname) > 50)|(len(patient.fullname) < 3):
		not_failed=False
	email_regex = re.compile("(\S+(@icahn.mssm.edu|@mssm.edu|@mountsinai.org)$)")
	if email_regex.match(str(patient.email))==None:
		not_failed=False
	lifenum_regex = re.compile("^(\d{7})$")
	if lifenum_regex.match(str(patient.lifenumber))==None:
		not_failed=False
	return not_failed

def send_survey_response_email(patient, record, app=app):
	'''send an email to reset the user's password'''
	# look for configuration variables in params.conf file...
	try:
		msg = Message(sender=config.mail_server_sender)
		msg.subject = record.survey.title + " taken on " + record.end_time.strftime('%B %-d, %Y')
		msg.sender  = config.mail_server_sender
		msg.recipients = [patient.email]
		record.end_time = record.end_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/New_York'))
		with app.app_context():
			if record.completed:
				msg.html = render_template('email_survey_complete.html', patient=patient,record=record)
				msg.body = render_template('email_survey_complete.txt', patient=patient,record=record)
			elif record.exited:
				msg.html = render_template('email_survey_exit.html', patient=patient,record=record) #change me!
				msg.body = render_template('email_survey_exit.txt', patient=patient,record=record) #change me!
		mail.send(msg)
	except:
		return None
	return None

@app.route("/", methods=['GET'])
@app.route("/index.html", methods=['GET'])
def index():
	g.patient = Patient.query.filter_by(mrn=g.patient_ident).first()
	if g.patient == None:
		flash("Your device appears to be unregistered. Please <a href='/patients/signup/1'>register</a> your device.")
	elif check_patient_identified(g.patient)==False:
		flash("Due to changes at Student Health, please <a href='/patients/edit/self'>update</a> your records before continuing.")
	return render_template("index.html")

@app.route("/about", methods=["GET"])
def about():
	return render_template("about.html")

@app.route('/surveys', methods=['GET'])
@flask_login.login_required
def serve_survey_index():
	'''GUI: serve the survey index page'''
	surveys = []
	for s in current_user.surveys:
		try:
			s.description_html = delta_html.render(json.loads(s.description)["ops"])
		except:
			s.description_html = '<p>' + s.description + '</p>'
		surveys.append(s)
	return render_template("surveys.html",
	                        surveys = surveys)

@app.route('/responses', methods=['GET'])
@flask_login.login_required
def serve_responses_index():
	'''GUI: serve the response index page'''
	today = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
	responses = QuestionResponse.query.filter(QuestionResponse.time>today).all()

	return render_template("responses.html",
							responses = responses)

### controller functions for surveys

@app.route('/surveys/new/', methods=['GET', 'POST'])
@flask_login.login_required
def add_survey():
	'''GUI: add a survey to the DB'''
	formobj = SurveyForm(request.form)
	if request.method == 'POST' and formobj.validate():
		dbobj = Survey(title=formobj.title.data, description=formobj.description.data)
		dbobj.user_id = current_user.id
		db_session.add(dbobj)
		db_session.commit()
		flash('Survey added.')
		return redirect(url_for('serve_survey_index'))
	return render_template("form.html", action="Add", data_type="a survey", form=formobj)

@app.route('/surveys/edit/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_survey(_id):
	'''GUI: edit a survey in the DB'''
	survey = Survey.query.get_or_404(_id)
	formout = SurveyForm(obj=survey)
	formobj = SurveyForm(request.form)
	if request.method == 'POST':
		survey.title = formobj.title.data
		survey.description = formobj.description.data
		db_session.add(survey)
		db_session.commit()
		flash('Survey edited.')
		return redirect(url_for('serve_survey_index'))
	return render_template("form.html", action="Edit", data_type=survey.title, form=formout)

@app.route('/surveys/<int:survey_id>/questions/sort', methods=["POST"])
@flask_login.login_required
def resort_survey(survey_id):
	question_order = urllib.parse.parse_qs(request.json)["question[]"]
	question_order = [Question.query.get(int(q)) for q in question_order]
	survey = Survey.query.get(question_order[0].survey_id)
	for ix,q in enumerate(question_order):
		if ix==0:
			survey.head = question_order[ix]
			db_session.add(survey)
		else:
			question_order[ix-1].next_q = question_order[ix]
			db_session.add(question_order[ix-1])
		if ix == len(question_order)-1:
			question_order[ix].next_q = None
			db_session.add(question_order[ix])
	db_session.commit()
	return b'Updated'

@app.route('/surveys/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_survey(_id):
    dbobj = Survey.query.get_or_404(_id)
    db_session.delete(dbobj)
    db_session.commit()
    flash('Survey removed.')
    return redirect(url_for('serve_survey_index'))

@app.route('/surveys/view/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def view_survey(_id):
    dbobj = Survey.query.get_or_404(_id)
    return render_template("view_survey.html", survey = dbobj)

@app.route('/surveys/start/<int:survey_id>', methods=['GET', 'POST'])
def start_survey(survey_id):
	'''TODO: need to select the patient which will be taking the survey. This will make this starting block a form.'''
	if g.patient == None:
		return redirect(url_for('patient_signup',survey_id=survey_id))
	if check_patient_identified(g.patient) ==False:
		flash("Please update your records before completing new screenings.")
		return redirect(url_for('edit_patient_self',next=request.path))
	session_id = randomword(32)
	while SurveyResponse.query.filter(SurveyResponse.session_id==session_id).count() > 0:
		session_id = randomword(32)
	u = request.values.get('u', g.patient.id)
	survey = Survey.query.get_or_404(survey_id)
	patients = None
	try:
		survey.description_html = delta_html.render(json.loads(survey.description)["ops"])
	except:
		survey.description_html = '<p>' + survey.description + '</p>'
	return render_template('start_survey.html', survey=survey, u = u, s = session_id, patients=patients)
	#return redirect(url_for(serve_survey), survey_id=_id, u=uniq_id)

@app.route('/surveys/serve/<int:survey_id>', methods=['GET', 'POST'])
def serve_survey(survey_id):
	survey = Survey.query.get_or_404(survey_id)
	if g.patient == None:
		return redirect(url_for('patient_signup',survey_id=survey_id))
	today = datetime.datetime.now().date()
	previous_responses = SurveyResponse.query.filter(SurveyResponse.uniq_id==g.patient.id).\
		filter(SurveyResponse.end_time.isnot(None),SurveyResponse.start_time>today).first()
	if (current_user.is_authenticated==False) & (previous_responses!=None):
		return render_template("survey_quit.html",survey=survey, patient=g.patient,message="You can only take the survey once per day.")

	survey_response_id = request.values.get("sr", None)
	question_id = request.values.get("question", None)
	uniq_id = request.values.get("u", None)
	sess = request.values.get("s", None)

	while SurveyResponse.query.filter(SurveyResponse.session_id==sess).count() > 1:
		sess = randomword(32)

	if survey.head == None:
		return render_template("view_survey.html", survey = survey)
	if question_id == None:
		question_id = survey.head.id
	question_id = int(question_id)
	question = Question.query.get_or_404(question_id)
	next_question = question.next_q.id if question.next_q != None else None
	last_question = question.prev_q.id if question.prev_q != None else None
	if survey_response_id==None:
		curuser = current_user.id if id in current_user.__dict__ else None
		survey_response = SurveyResponse(survey_id=survey.id, uniq_id=uniq_id, session_id=sess, user_id=curuser)
		db_session.add(survey_response)
		db_session.commit()
	else:
		survey_response = SurveyResponse.query.get_or_404(survey_response_id)
	formobj = QuestionView().get(question)
	if (request.method == 'POST') & (len(request.form.getlist("response"))!=0):
		#print("saving...")
		next_question, next_survey, exit, complete, message = save_response(request.form, question_id, session_id = sess, survey_response_id = survey_response.id)
		if next_question != None:
			return redirect(url_for("serve_survey",survey_id=survey.id,u=uniq_id,s=sess,sr=survey_response_id,question=next_question))
		if next_survey != None:
			return redirect(url_for('start_survey', survey_id=trigger_survey, u=uniq_id, s = sess))
		if exit:
			survey_response.exit()
			survey_response.message = message
			db_session.add(survey_response)
			db_session.commit()
			send_survey_response_email(g.patient,survey_response)
			return redirect(url_for("exit_survey", sr_id=survey_response.id, session_id=survey_response.session_id))
		if complete: ##complete survey!
			survey_response.complete()
			survey_response.message = message
			db_session.add(survey_response)
			db_session.commit()
			send_survey_response_email(g.patient,survey_response)
			return redirect(url_for("complete_survey", sr_id=survey_response.id, session_id=survey_response.session_id))
		return redirect(url_for('serve_survey', survey_id=survey_id, question=next_question, u=uniq_id, s=sess, sr = survey_response.id))
	else:
		#print(request.form.getlist("response"))
		#print(len(request.form.getlist("response")))
		#print(request.method)
		if (request.method == 'POST') & (len(request.form.getlist("response"))==0):
			#print("failed!!")
			flash("Please select a response")
		try:
			question.description_html = delta_html.render(json.loads(question.description)["ops"])
		except:
			question.description_html = '<p>' + question.description + '</p>'
		return render_template("serve_question.html", survey = survey, question = question,
		                       next_q = next_question, last_q = last_question, form=formobj, u=uniq_id, s = sess, sr = survey_response.id)

@app.route("/patients/self/reset")
def reset_device():
	response = make_response(redirect(url_for("index")))
	if g.patient_ident!=None:
		g.patient_ident = randomword(16)
		response.set_cookie('patient_ident', g.patient_ident, max_age=datetime.timedelta(weeks=52))
		device = Device(device_id = g.patient_ident)
		db.session.add(device)
		db.session.commit()
		g.device = device
		g.patient = None
		flash("Device ID reset. You will need to register with ISMMS Health Check again to complete surveys.")
	return response

@app.route("/exit/<int:sr_id>/<session_id>")
def exit_survey(sr_id,session_id):
	record = SurveyResponse.query.filter_by(id=sr_id,session_id=session_id,exited=1).first()
	if record==None:
		return abort(404,"Exit record not found.")
	survey = record.survey
	if current_user.is_authenticated:
		if record.exited:
			patient = record.patient
			qrcode_out = None
			#qrcode_out = qrcode(url_for('exit_survey',session_id=record.session_id,_external=True))
			return render_template("survey_exit.html",record=record, patient = patient,survey=survey,qrcode_out=qrcode_out)
		else:
			return abort(404,"Exit record not found.")
	if g.patient:
		if record.uniq_id != g.patient.id:
			return abort(401,"Your device isn't authorized to view this exit record.")
		else:
			if record.exited:
				qrcode_out = None
				#qrcode_out = qrcode(url_for('exit_survey',session_id=record.session_id,_external=True))
				return render_template("survey_exit.html",record=record, patient = g.patient,survey=survey,qrcode_out=qrcode_out)
			else:
				return abort(404,"Exit record not found.")
	else:
		return abort(401,"Your device appears to be unregistered. Only registered devices can view exit records.")

@app.route("/cr/<int:sr_id>/<session_id>")
def complete_survey(sr_id, session_id):
	record = SurveyResponse.query.filter_by(id=sr_id,session_id=session_id,completed=1).first()
	if record==None:
		return abort(404,"Completion record not found.")
	survey = record.survey
	if current_user.is_authenticated:
		if record.completed:
			patient = record.patient
			end_time = record.end_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/New_York'))
			day_num = end_time.timetuple().tm_yday % 46+1
			img_path = app.root_path+"/../assets/images/animals/animal%d.jpg"%day_num
			#qrcode_out = qrcode(url_for('complete_survey',session_id=record.session_id,_external=True),error_correction='Q',icon_img=img_path)
			qrcode_out = None
			return render_template("survey_complete.html",record=record, patient = patient,survey=survey,qrcode_out=qrcode_out)
		else:
			return abort(404,"Completion record not found.")
	if g.patient:
		if record.uniq_id != g.patient.id:
			return abort(401,"Your device isn't authorized to view this completion record.")
		else:
			if record.completed:
				end_time = record.end_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/New_York'))
				day_num = end_time.timetuple().tm_yday % 46+1
				img_path = app.root_path+"/../assets/images/animals/animal%d.jpg"%day_num
				#qrcode_out = qrcode(url_for('complete_survey',session_id=record.session_id,_external=True),error_correction='Q',icon_img=img_path)
				qrcode_out = None
				return render_template("survey_complete.html",record=record, patient = g.patient,survey=survey,qrcode_out=qrcode_out)
			else:
				return abort(404,"Completion record not found.")
	else:
		return abort(401,"Your device appears to be unregistered. Only registered devices can view completion records.")

def save_response(formdata, question_id, session_id=None, current_user = None, survey_response_id = None):
	#print(formdata.getlist("response"))
	question = Question.query.get_or_404(question_id)
	survey_response = SurveyResponse.query.get_or_404(survey_response_id)
	_response = QuestionResponse(
		response=formdata.getlist("response"),
		uniq_id=formdata["uniq_id"],
		session_id=session_id,
		question_id=question_id,
		survey_response_id=survey_response_id
	)
	responses = formdata.getlist("response")
	if (question.kind =="select") | (question.kind=="radio"):
			try:
				choices = json.loads(question.choices)
				for ix,r in enumerate(responses):
					responses[ix] = choices[r]
			except:
				print("ERROR: can't convert response ID to choice")
				pass
	_response.response = responses
	_response.user_id = Patient.query.get(formdata["uniq_id"]).user_id
	db_session.add(_response)
	db_session.commit()
	question = _response._question
	return run_trigger(question, _response)

### controller functions for questions

@app.route('/questions/new/', methods=['GET', 'POST'])
@flask_login.login_required
def add_question():
	'''GUI: add a question to a survey'''
	_id = request.values.get("survey", None)
	if _id == None:
		return abort(404,"Could not find survey matching that ID when adding question. Perhaps it was deleted?")
	survey = Survey.query.get_or_404(_id)
	survey_id = survey.id
	formobj = QuestionForm(request.form, survey_id=survey_id)
	formobj.survey_id.choices = [(s.id, s.title) for s in Survey.query]
	formobj.survey_id.data = survey.id
	if request.method == 'POST' and formobj.validate():
		dbobj = Question(
				body=formobj.body.data,
				description=formobj.description.data,
				choices=formobj.choices.data,
				image=None,
				kind=formobj.kind.data,
				survey_id = formobj.survey_id.data
		)
		dbobj.user_id = current_user.id
		dbobj.choices = json.dumps({str(ix):a for ix,a in enumerate(request.form.getlist("choices"))})
		if request.files["image"]:
			imgfile = request.files["image"]
			filename = secure_filename(imgfile.filename)
			imgfile.save(image_staticdir + filename)
			dbobj.image = filename
		db_session.add(dbobj)
		db_session.commit()
		survey, question = Survey.push(survey,dbobj)
		db_session.add(survey)
		db_session.add(question)
		db_session.commit()
		flash('Question added.')
		return redirect(url_for('view_survey', _id=survey_id))
	return render_template("form.html", action="Add", data_type="a question", form=formobj)

@app.route('/questions/edit/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_question(_id):
	'''GUI: edit a question in the DB'''
	question = Question.query.get_or_404(_id)
	survey = Survey.query.get_or_404(question.survey_id)
	survey_id = survey.id
	formout = QuestionForm(formdata=request.form, obj=question)
	formout.survey_id.choices = [(s.id, s.title) for s in Survey.query]
	if question.image == None:
		del formout.image_delete
	if request.method == 'POST' and formout.validate():
		question.kind = formout.kind.data
		question.survey_id = formout.survey_id.data
		question.body = formout.body.data
		question.description = formout.description.data
		question.choices = json.dumps({str(ix):a for ix,a in enumerate(request.form.getlist("choices"))})
		if formout.image_delete != None:
			if formout.image_delete.data==True:
				question.image = None
		if request.files["image"]:
			imgfile = request.files["image"]
			filename = secure_filename(imgfile.filename)
			imgfile.save(image_staticdir + filename)
			question.image = filename
		db_session.add(question)
		db_session.commit()
		flash('Question edited.')
		return redirect(url_for('view_survey', _id=survey_id))
	else:
		formout.survey_id.data = survey.id
		formout.kind.data = question.kind
		formout.image.data = question.image
	question_ids = [q.id for q in question.survey.questions()]
	curpos = str(question_ids.index(_id)+1)
	return render_template("form.html", action="Edit", data_type="question " + curpos, form=formout)

@app.route('/questions/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_question(_id):
    dbobj = Question.query.get_or_404(_id)
    survey = dbobj.survey
    edited = Survey.remove(survey,dbobj)
    for e in edited:
    	db_session.add(e)
    db_session.delete(dbobj)
    db_session.commit()
    flash('Question removed.')
    return redirect(url_for('view_survey', _id=survey.id))

### controller for patient functions
@app.route('/patients/signup/<int:survey_id>', methods=['GET', 'POST'])
def patient_signup(survey_id):
	'''GUI: add a patient to the DB via user sign up'''
	patient = Patient.query.filter_by(mrn=g.patient_ident).first()
	if patient == None:
		new_patient = True
		patient = Patient()
	else:
		new_patient = False
	formobj = PatientForm(obj=patient)
	if formobj.validate_on_submit():
		formobj.populate_obj(patient)
		link_survey = Survey.query.get_or_404(survey_id)
		link_user = link_survey.user
		patient.user = link_user
		patient.mrn = g.patient_ident
		db_session.add(patient)
		db_session.commit()
		flash("""You have registered this device and browser to take screenings.\n
		      You will need to use this same device and browser to submit future screenings and/or show compliance.\n
		      Do not clear your browser cookies from this device, or you will need to register your device again.\n
		      Please keep this ID for your records: %s"""% fmt_id(g.patient_ident))
		return redirect(url_for("start_survey",survey_id=survey_id))
	if new_patient:
		return render_template('form_signup_register.html', action="Register", data_type="device", form=formobj)
	else:
		if (patient.fullname != None) & (patient.fullname != ""):
			flash("Welcome back, %s! (ID:%s)" % (patient.fullname,fmt_id(patient.mrn)))
		else:
			flash("Welcome back! (ID:%s)" % fmt_id(patient.mrn))
		return redirect(url_for("start_survey",survey_id=survey_id))

##
@app.route('/patients/edit/<string:id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_patient(id=None):
	'''GUI: add a patient to the DB'''
	patient = Patient.query.filter_by(mrn=id).first_or_404()
	formobj = PatientEditForm(obj=patient)
	formobj.location.default = patient.location.code
	formobj.program.default = patient.program.code
	if formobj.validate_on_submit():
		formobj.populate_obj(patient)
		flash('Patient edited.')
		patient.user_id = current_user.id
		db_session.add(patient)
		db_session.commit()
		return redirect(url_for('view_patients'))
	return render_template("form.html", action="Edit", data_type="student", form=formobj)

@app.route('/patients/edit/self', methods=['GET', 'POST'])
def edit_patient_self():
	'''GUI: add a patient to the DB'''
	patient = g.patient
	if g.patient==None:
		abort(404, "This device is not registered.")
	formobj = PatientEditForm(obj=patient)
	formobj.location.default = patient.location.code
	formobj.program.default = patient.program.code
	if formobj.validate_on_submit():
		formobj.populate_obj(patient)
		flash('Successfully updated my records.')
		db_session.add(patient)
		db_session.commit()
		if 'next' in request.args:
			return redirect(request.values.get('next'))
		else:
			return redirect(url_for('view_patient_self'))
	return render_template("form_self_edit.html", action="Update", data_type="my records", form=formobj)

        #abort(403, "Editing your own information is temporarily disabled, please check back later.")
	#return redirect(url_for('view_patient_self'))

@app.route("/patients/")
@flask_login.login_required
def view_patients():
	today = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
	patients = Patient.query.join(SurveyResponse).filter(SurveyResponse.end_time.isnot(None),SurveyResponse.start_time>today).all()
	for p in patients:
		ls = p.surveys.order_by(SurveyResponse.end_time.desc()).first()
		p.last_seen = ls.start_time if ls else None
	status = dict()
	for p in patients:
		ptstat = 0
		taken = p.surveys.order_by(SurveyResponse.id.desc()).first()
		if taken!=None:
			if taken.completed:
				ptstat = 1
			if taken.exited:
				ptstat = -1
		status[p.id] = ptstat
	return render_template("patients.html", patients=patients, status = status)

@app.route("/patients/delete/<string:id>")
@flask_login.login_required
def delete_patient(id):
	patient = Patient.query.filter_by(mrn=id).first_or_404()
	db_session.delete(patient)
	db_session.commit()
	flash('Patient deleted.')
	return redirect(url_for('view_patients'))

@app.route('/patients/<int:id>/give_survey', methods=['GET'])
@flask_login.login_required
def patient_survey_selector(id):
	'''GUI: serve the survey select page for a patient'''
	patient = Patient.query.get_or_404(id)
	surveys = Patient.user.surveys
	for s in surveys:
		try:
			s.description_html = delta_html.render(json.loads(s.description)["ops"])
		except:
			s.description_html = '<p>' + s.description + '</p>'
	return render_template("surveys_selector.html",
	                    surveys = surveys,
	                    patient = patient)

### controller for trigger functions

@app.route('/triggers/new/', methods=['GET', 'POST'])
@flask_login.login_required
def add_trigger():
	'''GUI: add a trigger to the DB'''
	q = request.values.get("question", None)
	formobj = TriggerForm(request.form)
	trigger = Trigger()
	question = Question.query.get(q)
	formobj.question_id.data = question.id
	formobj.question_id.label = question.body
	for ix in range(len(formobj.conditions)):
		formobj.conditions[ix].subject.query = Survey.query.get(1)._questions
	formobj.dest_yes.query = Survey.query.get(1)._questions
	formobj.dest_no.query = Survey.query.get(1)._questions

	if request.method == 'POST' and formobj.validate():
		formobj.populate_obj(trigger)
		trigger.question_id = int(formobj.question_id.data)
		trigger.dest_yes = trigger.dest_yes.id if trigger.dest_yes else None
		trigger.dest_no = trigger.dest_no.id if trigger.dest_no else None
		for ix in range(len(trigger.conditions)):
			trigger.conditions[ix].subject_id = trigger.conditions[ix].subject.id
		db.session.add(trigger)
		db.session.commit()
		flash('Trigger added.')
		if q:
			return redirect(url_for('view_survey', _id=question.survey.id))
		else:
			return redirect(url_for('serve_survey_index'))
	else:
		formobj.conditions._add_entry()
		formobj.template = formobj.conditions[-1]
		formobj.template.subject.query = Survey.query.get(1)._questions
		if len(formobj.conditions)>1:
			formobj.conditions = formobj.conditions[0:-1]
	#formobj.questions.choices = [(q.id, "(ID: %s) "% str(q.id) + q.body) for q in Question.query]
	return render_template("form_trigger.html", action="Add", data_type="a trigger", form=formobj)

@app.route('/triggers/edit/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_trigger(_id):
	'''GUI: edit a trigger in the DB'''
	trigger = Trigger.query.get_or_404(_id)
	formobj = TriggerForm(request.form,obj=trigger)
	question = trigger.question
	formobj.dest_yes.query = trigger.question.survey._questions
	formobj.dest_no.query = trigger.question.survey._questions
	formobj.question_id.data = question.id
	formobj.question_id.label = question.body
	for ix in range(len(formobj.conditions)):
		formobj.conditions[ix].subject.query = Survey.query.get(1)._questions
	if request.method == 'POST' and formobj.validate():
		formobj.populate_obj(trigger)
		trigger.question_id = int(formobj.question_id.data)
		trigger.dest_yes = trigger.dest_yes.id if trigger.dest_yes else None
		trigger.dest_no = trigger.dest_no.id if trigger.dest_no else None
		for ix in range(len(trigger.conditions)):
			trigger.conditions[ix].subject_id = trigger.conditions[ix].subject.id
		db.session.add(trigger)
		db.session.commit()
		flash('Trigger edited.')
		return redirect(url_for('view_survey', _id=question.survey.id))
	else:
		formobj.alert_yes.data = trigger.alert_yes
		formobj.alert_no.data = trigger.alert_no
		formobj.yes_type.data = trigger.yes_type
		formobj.no_type.data = trigger.no_type
		formobj.dest_yes.data = Question.query.get(trigger.dest_yes) if trigger.dest_yes else None
		formobj.dest_no.data = Question.query.get(trigger.dest_no) if trigger.dest_no else None

		formobj.conditions._add_entry()
		formobj.template = formobj.conditions[-1]
		formobj.template.subject.query = Survey.query.get(1)._questions
		if len(formobj.conditions)>1:
			formobj.conditions = formobj.conditions[0:-1]
	#formobj.questions.choices = [(q.id, "(ID: %s) "% str(q.id) + q.body) for q in Question.query]
	return render_template("form_trigger.html", action="Edit", data_type="trigger", form=formobj)

@app.route('/triggers/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_trigger(_id):
    dbobj = Trigger.query.get_or_404(_id)
    db_session.delete(dbobj)
    db_session.commit()
    flash('Trigger removed.')
    if request.referrer == None:
    	return redirect(url_for('serve_survey_index'))
    else:
    	return redirect(request.referrer)

@app.route('/responses/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_response(_id):
    dbobj = QuestionResponse.query.get_or_404(_id)
    patient_id = dbobj.uniq_id
    db_session.delete(dbobj)
    db_session.commit()
    flash('Response removed.')
    if request.referrer == None:
    	return redirect(url_for('view_patient', id=patient_id))
    else:
    	return redirect(request.referrer)

### static files (only when not running under Apache)

@app.route('/assets/<path:path>')
def send_js(path):
    return send_from_directory(base_dir+'/assets', path)

@app.route('/manifest.json')
def send_manifest():
    return send_from_directory(base_dir+'/assets','manifest.json')

@app.route("/.well-known/<path:path>")
def send_certbot(path):
    return send_from_directory(base_dir+'/assets',path)

@app.route('/patient_feed/', methods=["GET", "POST"])
@app.route('/patient_feed/<int:id>/', methods=["GET", "POST"])
@flask_login.login_required
def patient_feed(id=None):
	if id:
		patients = Patient.query.filter_by(id=id)
	else:
		patients = current_user.patients
	patients_feed = []
	for p in patients:
		responses = p.responses
		for r in responses:
			if r.question_id != None:
				question = Question.query.get(r.question_id)
				patients_feed.append((r.time.strftime("%Y-%m-%d %H:%M:%S"), p.id, r.session_id, question.body, question.kind.code, r.response))
			else:
				patients_feed.append((r.time.strftime("%Y-%m-%d %H:%M:%S"), p.id, r.session_id, None, None, r.response))
	patients_feed = sorted(patients_feed, key=lambda x:x[0])
	return json.dumps(patients_feed)

@app.route('/patients/<int:id>', methods=["GET", "POST"])
@flask_login.login_required
def view_patient(id):
	p = Patient.query.get_or_404(id)
	ls = p.surveys.order_by(SurveyResponse.end_time.desc()).first()
	p.last_seen = ls.start_time if ls else None
	patients_feed = []
	for s in p.surveys:
		patients_feed.append((s.start_time.strftime("%Y-%m-%d %H:%M:%S"),"patient", s))
	comments = Comment.query.filter_by(patient_id=p.id)
	for c in comments:
		patients_feed.append((c.time.strftime("%Y-%m-%d %H:%M:%S"), "comment", c))
	patients_feed = sorted(patients_feed, key=lambda x:x[0],reverse=False)
	today = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
	ptstat = 0
	taken = p.surveys.filter(SurveyResponse.end_time.isnot(None),
	                         SurveyResponse.start_time>today).order_by(SurveyResponse.id.desc()).first()
	if taken!=None:
		if taken.completed:
			ptstat = 1
		if taken.exited:
			ptstat = -1
	return render_template('view_patient.html', patients_feed = patients_feed, patient=p, status=ptstat)

@app.route('/patients/self', methods=["GET", "POST"])
def view_patient_self():
	if g.patient == None:
		return abort(401,"Please register your device first, then come back to this page.")
	p = g.patient
	patients_feed = []
	for s in p.surveys.all():
		patients_feed.append((s.start_time.strftime("%Y-%m-%d %H:%M:%S"),"patient", s))
	patients_feed = sorted(patients_feed, key=lambda x:x[0],reverse=True)
	status = sum([1-i.complete for i in p.progress])
	return render_template('view_patient_self.html', patients_feed = patients_feed, patient=p, status=status)

@app.route('/comment/add/<int:patient_id>/', methods=["GET", "POST"])
@flask_login.login_required
def add_comment(patient_id):
	user_id = current_user.id
	if patient_id not in [i.id for i in current_user.patients]:
		return abort(404,"Comment not found with that ID.")
	if request.method == 'POST':
		body = request.form["body"] if request.form["body"] != "" else None
	if body:
		comment = Comment(body=body, patient_id=patient_id, user_id=user_id)
		db_session.add(comment)
		db_session.commit()
		return redirect(url_for('view_patient', id=patient_id))
	else:
		return abort(400, "Couldn't add comment.")

@app.route('/comment/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_comment(_id):
    dbobj = Comment.query.get_or_404(_id)
    patient_id = dbobj.patient_id
    db_session.delete(dbobj)
    db_session.commit()
    flash('Comment removed.')
    return redirect(url_for('view_patient', id=patient_id))

@app.route("/surveys/<int:survey_id>/responses/dashboard/")
def loading(survey_id):
	start_request = request.values.get("start_date","2020-06-29")
	end_request = request.values.get("end_date",None)
	dest_url = "/surveys/"+str(survey_id)+"/responses/dashboard/loaded?"
	if start_request:
		dest_url += "start_date="+start_request+"&"
	if end_request:
		dest_url += "end_date="+end_request
	return render_template("loading.html",dest_url=dest_url)

def make_cache_key(*args, **kwargs):
    path = request.path
    args = str(hash(frozenset(request.args.items())))
    responses = str(models.SurveyResponse.query.count())
    if current_user.is_authenticated:
    	return (path+args+responses+"user"+str(current_user.id)).encode('utf-8')
    else:
    	return (path +args+responses).encode('utf-8')

@app.route("/surveys/<int:survey_id>/responses/dashboard/loaded",methods=["GET"])
@flask_login.login_required
#@cache.cached(timeout=None,key_prefix=make_cache_key)
def survey_response_dashboard(survey_id):
	start_request = request.values.get("start_date","2020-06-29")
	end_request = request.values.get("end_date",(datetime.datetime.now(tz)).date().strftime("%Y-%m-%d"))
	dash_figs = []
	question_figs = []

	try:
	    start_time = (datetime.datetime.strptime(start_request,"%Y-%m-%d")).date() if start_request != None else (datetime.datetime.now()-datetime.timedelta(days=30)).date()
	    end_time = (datetime.datetime.strptime(end_request,"%Y-%m-%d")).date() if end_request != None else (datetime.datetime.now(tz)).date()
	except:
	    start_time = (datetime.datetime.now()-datetime.timedelta(days=30)).date()
	    end_time = (datetime.datetime.now(tz)).date()

	time_end = end_time.timetuple()
	time_start = start_time.timetuple()
	time_end = datetime.datetime.fromtimestamp(time.mktime(time_end)).replace(tzinfo=pytztimezone('EST')).astimezone(pytztimezone("UTC"))
	time_start = datetime.datetime.fromtimestamp(time.mktime(time_start)).replace(tzinfo=pytztimezone('EST')).astimezone(pytztimezone("UTC"))

	survey = models.Survey.query.get_or_404(survey_id)

	def pt_to_pd():
	    res = [dict(r) for r in db.session.execute(models.Patient.query.statement)]
	    return pd.DataFrame(res)

	sig_r = db.session.query(models.Patient)\
	    .join(models.SurveyResponse)\
	    .filter(models.SurveyResponse.survey_id==survey.id)\
	    .filter(func.substr(models.SurveyResponse.end_time,0,11)==end_request)\
	    .filter(models.SurveyResponse.exited==True).all()

	cols = [func.substr(models.SurveyResponse.end_time,0,11),
	        func.count(func.distinct(models.SurveyResponse.uniq_id)).label("per_date"),
	       models.SurveyResponse.completed,
	       models.SurveyResponse.exited]
	q = db.session.query(*cols).join(models.Patient)\
		    .filter(models.SurveyResponse.start_time > time_start)\
	        .filter(models.SurveyResponse.start_time <= (time_end+datetime.timedelta(days=1)))\
	        .filter(models.SurveyResponse.end_time > time_start)\
	        .filter(models.SurveyResponse.end_time <= (time_end+datetime.timedelta(days=1)))\
	        .filter(models.SurveyResponse.end_time != None)\
	        .group_by(func.substr(models.SurveyResponse.end_time,0,11),
	                  models.SurveyResponse.completed,models.SurveyResponse.exited,)
	df_q = pd.read_sql(q.statement,con=db.engine)
	df_q_2 = df_q.pivot_table(index="substr_1",columns=["completed","exited"],values="per_date",aggfunc='sum').fillna(0)
	df_q_2.columns = ["daily_exited_surveys","daily_completed_surveys"]
	df_q_2["daily_total_surveys"] = df_q_2["daily_exited_surveys"]+df_q_2["daily_completed_surveys"]
	df_q_2["positivity_rate"] = df_q_2["daily_exited_surveys"]/df_q_2["daily_total_surveys"]*100
	df_q_2["fmt_date"] = df_q_2.index
	df_q_2.index = [datetime.datetime.strptime(a,"%Y-%m-%d").strftime("%D") for a in df_q_2.index]
	df = df_q_2.reset_index()
	if end_request in list(df["fmt_date"]):
		df = df.loc[df.index[0]:df[df["fmt_date"]==end_request].index[0]]
	df2 = df.loc[:,["index","daily_completed_surveys","daily_exited_surveys"]]
	df2.columns = ["index","Cleared","Sent Home"]
	df3 = df2.melt(id_vars="index")

	if len(df) > 0:
	    pts = pt_to_pd()

	    pts.creation_time = pts.creation_time.dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
	    pts_df = pts.set_index("creation_time")
	    
	    cols = [func.substr(models.SurveyResponse.end_time,0,11),
	        func.count(func.distinct(models.SurveyResponse.uniq_id)).label("per_date"),
	        models.Patient.year,
	        models.SurveyResponse.completed,
	        models.SurveyResponse.exited]
	    q = db.session.query(*cols).join(models.Patient)\
			.filter(models.SurveyResponse.start_time > time_start)\
			.filter(models.SurveyResponse.start_time <= (time_end+datetime.timedelta(days=1)))\
			.filter(models.SurveyResponse.end_time > time_start)\
			.filter(models.SurveyResponse.end_time <= (time_end+datetime.timedelta(days=1)))\
			.filter(models.SurveyResponse.end_time != None)\
			.group_by(models.Patient.year, func.substr(models.SurveyResponse.end_time,0,11),
			          models.SurveyResponse.completed,models.SurveyResponse.exited,)
	    df_q = pd.read_sql(q.statement,con=db.engine)
	    df_q_2 = df_q.pivot_table(index=["substr_1","year"],columns=["completed","exited"],values="per_date",aggfunc='sum').fillna(0)
	    df_q_2.columns = ["exited","completed"]
	    df_q_2["responded"] = df_q_2["exited"] + df_q_2["completed"]
	    outdf_year = df_q_2.reset_index().loc[:,["substr_1","year","responded","completed","exited"]]
	    outdf_year = outdf_year[[i in list(range(2021,2025)) for i in outdf_year["year"]]]
	    
	    cols = [func.substr(models.SurveyResponse.end_time,0,11),
	        func.count(func.distinct(models.SurveyResponse.uniq_id)).label("per_date"),
	        models.Patient.year,
	        models.SurveyResponse.completed,
	        models.SurveyResponse.exited]
	    q = db.session.query(*cols).join(models.Patient)\
			.filter(models.SurveyResponse.start_time > time_start)\
			.filter(models.SurveyResponse.start_time <= (time_end+datetime.timedelta(days=1)))\
			.filter(models.SurveyResponse.end_time > time_start)\
			.filter(models.SurveyResponse.end_time <= (time_end+datetime.timedelta(days=1)))\
			.filter(models.SurveyResponse.end_time != None)\
			.group_by(models.Patient.year, func.substr(models.SurveyResponse.end_time,0,11),
			          models.SurveyResponse.completed,models.SurveyResponse.exited,)
	    df_q = pd.read_sql(q.statement,con=db.engine)
	    df_q_2 = df_q.pivot_table(index=["substr_1","year"],columns=["completed","exited"]).fillna(0)
	    df_q_2.columns = ["exited","completed"]
	    df_q_2["responded"] = df_q_2["exited"] + df_q_2["completed"]
	    outdf_yr = df_q_2.reset_index().loc[:,["substr_1","year","responded","completed","exited"]]
	    outdf_yr.columns = ["date","year","total_responded","Well","Sick"]
	    
	    cols = [func.substr(models.SurveyResponse.end_time,0,11),
	        func.count(models.SurveyResponse.uniq_id).label("per_date"),
	        models.Patient.program,
	        models.SurveyResponse.completed,
	        models.SurveyResponse.exited]
	    q = db.session.query(*cols).join(models.Patient)\
			.filter(models.SurveyResponse.start_time > time_start)\
			.filter(models.SurveyResponse.start_time <= (time_end+datetime.timedelta(days=1)))\
			.filter(models.SurveyResponse.end_time > time_start)\
			.filter(models.SurveyResponse.end_time <= (time_end+datetime.timedelta(days=1)))\
			.filter(models.SurveyResponse.end_time != None)\
			.group_by(models.Patient.program, func.substr(models.SurveyResponse.end_time,0,11),
			          models.SurveyResponse.completed,models.SurveyResponse.exited,)
	    df_q = pd.read_sql(q.statement,con=db.engine)
	    df_q["program"] = list([str(a) for a in df_q["program"]])
	    df_q_2 = df_q.pivot_table(index=["substr_1","program"],columns=["completed","exited"],values="per_date",aggfunc='sum').fillna(0)
	    df_q_2.columns = ["exited","completed"]
	    df_q_2["responded"] = df_q_2["exited"] + df_q_2["completed"]
	    outdf_p = df_q_2.reset_index().loc[:,["substr_1","program","responded","completed","exited"]]
	    outdf_p.columns = ["date","program","total_responded","Well","Sick"]
	    
	    cols = [func.substr(models.SurveyResponse.end_time,0,11),
	        func.count(models.SurveyResponse.uniq_id).label("per_date"),
	        models.Patient.location,
	        models.SurveyResponse.completed,
	        models.SurveyResponse.exited]
	    q = db.session.query(*cols).join(models.Patient)\
		        .filter(models.SurveyResponse.start_time > time_start)\
		        .filter(models.SurveyResponse.start_time <= (time_end+datetime.timedelta(days=1)))\
		        .filter(models.SurveyResponse.end_time > time_start)\
		        .filter(models.SurveyResponse.end_time <= (time_end+datetime.timedelta(days=1)))\
		        .filter(models.SurveyResponse.end_time != None)\
		        .group_by(models.Patient.program, func.substr(models.SurveyResponse.end_time,0,11),
		                  models.SurveyResponse.completed,models.SurveyResponse.exited,)
	    df_q = pd.read_sql(q.statement,con=db.engine)
	    df_q["location"] = list([str(a) for a in df_q["location"]])
	    df_q_2 = df_q.pivot_table(index=["substr_1","location"],columns=["completed","exited"],values="per_date",aggfunc='sum').fillna(0)
	    df_q_2.columns = ["exited","completed"]
	    df_q_2["responded"] = df_q_2["exited"] + df_q_2["completed"]
	    outdf_l = df_q_2.reset_index().loc[:,["substr_1","location","responded","completed","exited"]]
	    outdf_l.columns = ["date","location","total_responded","Well","Sick"]

	    outdf = outdf_yr
	    todaydf = outdf[outdf["date"]==str(end_time)].loc[:,["year","Well","Sick"]].melt(id_vars="year")

	    fig1 = plotlyBarplot(data=todaydf,x="year",y="value",hue="variable",stacked=True,ylabel="# Students",xlabel="Expected Graduation",
	                 title="Screenings by Year",colors=["red","green"],height=425,width=None,show_legend=True)
	    fig1.update_layout(legend=dict(
	      orientation="h",
	      yanchor="bottom",
	      y=1.02,
	      xanchor="right",
	      x=1
	     ))
	    outdf = outdf_p
	    todaydf = outdf[outdf["date"]==str(end_time)].loc[:,["program","Well","Sick"]].melt(id_vars="program")

	    fig2 = plotlyBarplot(data=todaydf,x="program",y="value",hue="variable",stacked=True,ylabel="# Students",xlabel="Expected Graduation",
	                 title="Screenings by Program",colors=["red","green"],height=500,width=None,show_legend=True)
	    fig2.update_layout(legend=dict(
	      orientation="h",
	      yanchor="bottom",
	      y=1.02,
	      xanchor="right",
	      x=1
	     ))
	    outdf = outdf_l
	    todaydf = outdf[outdf["date"]==str(end_time)].loc[:,["location","Well","Sick"]].melt(id_vars="location")

	    fig3 = plotlyBarplot(data=todaydf,x="location",y="value",hue="variable",stacked=True,ylabel="# Students",xlabel="Expected Graduation",
	                 title="Screenings by Location",colors=["red","green"],height=500,width=None,show_legend=True)
	    fig3.update_layout(legend=dict(
	      orientation="h",
	      yanchor="bottom",
	      y=1.02,
	      xanchor="right",
	      x=1
	     ))
	    #outdf["date"] = [datetime.datetime.strftime(a,"%D") for a in outdf["date"]]
	    #fig1 = plotlyBarplot(data=outdf,x="date",y="total_registered",hue="year",stacked=True,width=None,height=400,
	    #                     title="Students Registered",ylabel="# Students",show_legend=True,xlabel="Date")
	 
	    dash_figs = [fig1,fig2,fig3]

	    patient_count = models.Patient.query.count()
	    if end_request in list(df["fmt_date"]):
	        df = df.loc[df.index[0]:df[df["fmt_date"]==end_request].index[0]]
	        today_count = int(list(df["daily_total_surveys"])[-1])
	        today_pct = list(df["positivity_rate"])[-1]
	        week_count = int(sum(list(df["daily_total_surveys"])[-7:]))
	        week_pct = sum(list(df["positivity_rate"])[-7:])/7
	        today_positive = int(list(df["daily_exited_surveys"])[-1])
	        today_negative = int(list(df["daily_completed_surveys"])[-1])
	        today_pct_pos = today_pct
	    else:
	        today_count = 0
	        today_pct = 0
	        week_count = 0
	        week_pct = 0
	        patient_count = 0
	        today_positive = 0
	        today_negative = 0
	        today_pct_pos = 0

	    special_figs = []
	    last7_figs = []
	    from scipy import signal
	    def pos_plot(df,width=None,height=400):
	        layout = go.Layout(
	                    autosize=True,
	                    width=width,
	                    height=height,
	                title={'text': 'Percent Positivity Rate',
	                        'y':0.9,
	                        'x':0.5,
	                        'xanchor': 'center',
	                        'yanchor': 'top'}
	                )
	        fig = go.Figure(layout=layout)
	        fig.add_trace(go.Scatter(x=df["index"], y=df["positivity_rate"],line_shape='hv',name="Values"))
	        try:
	            fig.add_trace(go.Scatter(x=df["index"], y=df["positivity_rate"].rolling(window=7,min_periods=1).mean(),line_shape='spline',
	                                name="Average (7 days)"))
	        except ValueError as err:
	            pass
	        fig.update_layout( xaxis_title='Date',
	                           yaxis_title='Positivity Rate %')
	        fig.update_layout(legend=dict(
	          orientation="h",
	          yanchor="bottom",
	          y=1.02,
	          xanchor="right",
	          x=1
	         ))
	        return fig
	    special_figs.append(pos_plot(df))
	    fig = plotlyBarplot(data=df3,x="index",y="value",hue="variable",width=None, height=400,
	                             title="Compliance History",stacked=True,show_legend=True,colors=["green","red"],
	                             ylabel="# Students",xlabel="Date")
	    fig.update_layout(legend=dict(
	          orientation="h",
	          yanchor="bottom",
	          y=1.02,
	          xanchor="right",
	          x=1
	         ))
	    special_figs.append(fig)

	else:
	    dash_figs = []
	    special_figs = []
	    last7_figs = []
	    today_count = 0
	    today_pct = 0
	    week_count = 0
	    week_pct = 0
	    patient_count = 0
	    today_positive = 0
	    today_negative = 0
	    today_pct_pos = 0

	#device_count = len(devices)

	cols = [func.substr(models.QuestionResponse.time,0,11),
	        models.QuestionResponse.id,
	        models.QuestionResponse.uniq_id,
	        models.QuestionResponse._response,
	        models.QuestionResponse.question_id,
	        models.Question.body,
	       models.Question.choices,
	       models.Question.kind]
	sr = db.session.query(*cols)\
	    .join(models.Question,models.SurveyResponse)\
	    .filter(models.SurveyResponse.survey_id==survey.id)\
	    .filter(models.SurveyResponse.start_time > time_start)\
	    .filter(models.SurveyResponse.start_time <= time_end)\
	    .filter(models.SurveyResponse.end_time > time_start)\
	    .filter(models.SurveyResponse.end_time <= time_end)

	df_q = pd.read_sql(sr.statement,con=db.engine)
	df_q.columns = ["date","response_id","uniq_id","response","question_id","question_title","question_choices","question_type"]
	qres = df_q

	if len(qres)>0:
	    qres = qres.groupby(["date","question_id","uniq_id"]).first()
	    qres = qres.reset_index()
	    e = [str(a.date()) for a in list(pd.date_range(start_time,end_time))]

	    for n,g in qres.groupby("question_id"):
	        title = list(g.question_title)[0]
	        choices = list(g.question_choices)[0]
	        choices = ast.literal_eval(choices) if choices != "" else {}
	        kind = list(g.question_type)[0]
	        xtype = "category"
	        pltdf = g.loc[:,["date","response"]]
	        pltdf["count"] = 1
	        pltdf.sort_values("date",inplace=True)
	        pltdf["date"] = pltdf["date"].astype(str)
	        refmt = []
	        for ix,row in pltdf.iterrows():
	            row = list(row)
	            for rr in row[1].split(";"):
	                refmt.append([row[0],rr,row[2]])
	        pltdf = pd.DataFrame(refmt,columns=pltdf.columns)
	        pltdf.set_index("date",inplace=True)
	        for ix in e:
	            if ix not in pltdf.index:
	                pltdf.loc[ix] = [None,0]
	        pltdf.sort_index(inplace=True)
	        pltdf.reset_index(inplace=True)
	        pltdf=pltdf.fillna(method="bfill")
	        fig = plotlyBarplot(data=pltdf,x="date",y="count",hue="response",
	                            xtype=xtype,grouped=True,ordered=False,stacked=True,order2=True,width=None,height=None,show_legend=True,ylabel="# Responses",xlabel="Date",title=title)
	        last7_figs.append(fig)



	for ix,fig in enumerate(dash_figs):
		dash_figs[ix] = offline.plot(fig,show_link=False, output_type="div", include_plotlyjs=False)
	for ix,fig in enumerate(question_figs):
		question_figs[ix] = offline.plot(fig,show_link=False, output_type="div", include_plotlyjs=False)
	for ix,fig in enumerate(special_figs):
		special_figs[ix] = offline.plot(fig,show_link=False, output_type="div", include_plotlyjs=False)
	for ix,fig in enumerate(last7_figs):
		last7_figs[ix] = offline.plot(fig,show_link=False, output_type="div", include_plotlyjs=False)
	start_time = datetime.datetime.strftime(start_time,"%Y-%m-%d")
	end_time = datetime.datetime.strftime(end_time,"%Y-%m-%d")
	return render_template("dashboard.html",dash_figs = dash_figs, question_figs = question_figs,
	                       last7_figs=last7_figs,patient_count=patient_count,device_count=0,
	                       today_count=today_count, today_pct=today_pct, week_count=week_count,
	                       week_pct=week_pct, survey=survey, start_date = start_time, end_date=end_time,
	                       today_positive=today_positive,today_negative = today_negative,
	                       today_pct_pos=today_pct_pos, patients = sig_r,special_figs=special_figs)

@app.route("/covid/dashboard",methods=["GET"])
#@cache.cached(timeout=None,key_prefix=make_cache_key)
def survey_response_student_dashboard():
	survey_id = 1
	start_request = request.values.get("start_date","2020-06-29")
	end_request = request.values.get("end_date",(datetime.datetime.now(tz)).date().strftime("%Y-%m-%d"))
	dash_figs = []
	question_figs = []
	if(True):
		try:
		    start_time = (datetime.datetime.strptime(start_request,"%Y-%m-%d")).date() if start_request != None else (datetime.datetime.now()-datetime.timedelta(days=30)).date()
		    end_time = (datetime.datetime.strptime(end_request,"%Y-%m-%d")).date() if end_request != None else (datetime.datetime.now(tz)).date()
		except:
		    start_time = (datetime.datetime.now()-datetime.timedelta(days=30)).date()
		    end_time = (datetime.datetime.now(tz)).date()

		time_end = end_time.timetuple()
		time_start = start_time.timetuple()
		time_end = datetime.datetime.fromtimestamp(time.mktime(time_end)).replace(tzinfo=pytztimezone('EST')).astimezone(pytztimezone("UTC"))
		time_start = datetime.datetime.fromtimestamp(time.mktime(time_start)).replace(tzinfo=pytztimezone('EST')).astimezone(pytztimezone("UTC"))

		survey = models.Survey.query.get_or_404(survey_id)

		cols = [func.substr(models.SurveyResponse.end_time,0,11),
		        func.count(func.distinct(models.SurveyResponse.uniq_id)).label("per_date"),
		       models.SurveyResponse.completed,
		       models.SurveyResponse.exited]
		q = db.session.query(*cols).join(models.Patient)\
		        .filter(models.SurveyResponse.end_time > time_start)\
		        .filter(models.SurveyResponse.end_time <= (time_end+datetime.timedelta(days=1)))\
		        .filter(models.SurveyResponse.end_time != None)\
		        .group_by(func.substr(models.SurveyResponse.end_time,0,11),
		                  models.SurveyResponse.completed,models.SurveyResponse.exited,)
		df_q = pd.read_sql(q.statement,con=db.engine)
		df_q_2 = df_q.pivot_table(index="substr_1",columns=["completed","exited"],values="per_date",aggfunc='sum').fillna(0)
		df_q_2.columns = ["daily_exited_surveys","daily_completed_surveys"]
		df_q_2["daily_total_surveys"] = df_q_2["daily_exited_surveys"]+df_q_2["daily_completed_surveys"]
		df_q_2["positivity_rate"] = df_q_2["daily_exited_surveys"]/df_q_2["daily_total_surveys"]*100
		df_q_2["fmt_date"] = df_q_2.index
		df_q_2.index = [datetime.datetime.strptime(a,"%Y-%m-%d").strftime("%D") for a in df_q_2.index]
		df = df_q_2.reset_index()
		df2 = df.loc[:,["index","daily_completed_surveys","daily_exited_surveys"]]
		df2.columns = ["index","Cleared","Sent Home"]
		df3 = df2.melt(id_vars="index")

		#device_count = len(devices)

		special_figs = []
		last7_figs = []
		from scipy import signal
		def pos_plot(df,width=None,height=400):
		    layout = go.Layout(
		                autosize=True,
		                width=width,
		                height=height,
		            title={'text': 'Percent Positive Screenings',
		                    'y':0.9,
		                    'x':0.5,
		                    'xanchor': 'center',
		                    'yanchor': 'top'}
		            )
		    fig = go.Figure(layout=layout)
		    fig.add_trace(go.Scatter(x=df["index"], y=df["positivity_rate"],line_shape='hv',name="Values"))
		    try:
		    	fig.add_trace(go.Scatter(x=df["index"], y=df["positivity_rate"].rolling(window=7,min_periods=1).mean(),line_shape='spline',
		                            name="Average (7 days)"))
		    except ValueError as err:
		        pass
		    fig.update_layout( xaxis_title='Date',
		                       yaxis_title='Positivity Rate %')
		    fig.update_layout(legend=dict(
		      orientation="h",
		      yanchor="bottom",
		      y=1.02,
		      xanchor="right",
		      x=1,
		     ))
		    fig.update_layout(margin=dict(r=0,l=0))
		    return fig
		special_figs.append(pos_plot(df))
		fig = plotlyBarplot(data=df3,x="index",y="value",hue="variable",width=None, height=400,
			                     title="Compliance History",stacked=True,show_legend=True,colors=["green","red"],
			                     ylabel="# Students",xlabel="Date",margins=dict(r=0,l=0))
		fig.update_layout(legend=dict(
		      orientation="h",
		      yanchor="bottom",
		      y=1.02,
		      xanchor="right",
		      x=1
		     ))
		special_figs.append(fig)

		##special COVID tracking stats - NYC area
		special_figs_2 = []
		special_figs_2.append(plotly.io.read_json(open("medtracker/data/daily_cases.json","r")))
		special_figs_2.append(plotly.io.read_json(open("medtracker/data/r0_estimate.json","r")))		

		for ix,fig in enumerate(special_figs):
			special_figs[ix] = offline.plot(fig,show_link=False, output_type="div", include_plotlyjs=False)
		for ix,fig in enumerate(special_figs_2):
			special_figs_2[ix] = offline.plot(fig,show_link=False, output_type="div", include_plotlyjs=False)

		patient_count = models.Patient.query.count()
		if end_request in list(df["fmt_date"]):
			df = df.loc[df.index[0]:df[df["fmt_date"]==end_request].index[0]]
			today_count = int(list(df["daily_total_surveys"])[-1])
			today_pct = list(df["positivity_rate"])[-1]
			week_count = int(sum(list(df["daily_total_surveys"])[-7:]))
			week_pct = sum(list(df["positivity_rate"])[-7:])/7
			today_positive = int(list(df["daily_exited_surveys"])[-1])
			today_negative = int(list(df["daily_completed_surveys"])[-1])
			today_pct_pos = today_pct
		else:
			today_count = 0
			today_pct = 0
			week_count = 0
			week_pct = 0
			patient_count = 0
			today_positive = 0
			today_negative = 0
			today_pct_pos = 0

	else:
		dash_figs = []
		special_figs = []
		last7_figs = []
		today_count = 0
		today_pct = 0
		week_count = 0
		week_pct = 0
		patient_count = 0
		today_positive = 0
		today_negative = 0
		today_pct_pos = 0

	start_time = datetime.datetime.strftime(start_time,"%Y-%m-%d")
	end_time = datetime.datetime.strftime(end_time,"%Y-%m-%d")
	return render_template("dashboard_student.html",
	                       patient_count=patient_count,device_count=0,
	                       today_count=today_count, today_pct=today_pct, week_count=week_count,
	                       week_pct=week_pct, survey=survey, start_date = start_time, end_date=end_time,
	                       today_positive=today_positive,today_negative = today_negative,
	                       today_pct_pos=today_pct_pos, special_figs=special_figs,special_figs_2=special_figs_2)


def plotlyBarplot(x=None,y=None,hue=None,data=None,ylabel="",xlabel="",title="",
                    width=600,height=400,colors=["rgba"+str(tuple(i[0:3])) for i in cm.get_cmap("Set1").colors+cm.get_cmap("Set2").colors+cm.get_cmap("Set3").colors],
                    stacked=False,percent=False,ordered=False,xtype="category",grouped=False,order2=False,show_legend=False,margins = None):
    yaxis=go.layout.YAxis(
            title=ylabel,
            automargin=True,
            titlefont=dict(size=12),
        )

    xaxis=go.layout.XAxis(
            title=xlabel,
            automargin=True,
            titlefont=dict(size=12),
            type=xtype
        )
    if type(margins)==dict:
        margin = go.Margin(**margins)
        layout = go.Layout(
            autosize=True,
            width=width,
            height=height,
            yaxis=yaxis,
            xaxis=xaxis,
            margin=margin
        )
    else:
    	layout = go.Layout(
            autosize=True,
            width=width,
            height=height,
            yaxis=yaxis,
            xaxis=xaxis
        )
    titledict= {'text': title,
            'y':0.9,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'}

    fig = go.Figure(layout=layout)
    fig.update_layout(xaxis_type = xtype)
    ylab = y
    xlab = x

    ix = 0
    catorder = list(data.groupby(xlab).sum().index)
    if hue != None:
        #data = data[[type(i)!=float for i in data[hue]]]
        if percent:
            totalcounts = data.groupby(xlab).sum()[ylab]
        for hue,group in data.groupby(hue):
            counts = group.groupby(xlab).sum()[ylab]
            if percent:
                counts = round(counts/totalcounts.loc[counts.index,]*100,1)
            x = [str(i) for i in counts.index]
            y = counts.values
            name = str(hue)[0:8] + ".." if len(str(hue))>10 else str(hue)
            trace = go.Bar(x=x,y=y,
                           text=y,
                           textposition='auto',
                           orientation='v',
                         marker=dict(color=colors[ix]),
                         name="%s"%name)
            ix += 1
            fig.add_trace(trace)
    else:
        if grouped:
            counts = data.groupby(xlab).sum()[ylab]
            x = [str(i) for i in counts.index]
        else:
            counts = data[ylab]
            x = [str(i) for i in data[xlab]]
        y = counts.values
        name = str(ylabel)[0:8] + ".." if len(str(ylabel))>10 else str(ylabel)
        trace = go.Bar(x=x,y=y,
                       text=y,
                       textposition='auto',
                       orientation='v',
                     marker=dict(color=colors[ix]),
                     name="%s"%name)
        ix += 1
        fig.add_trace(trace)
    fig.update_layout(title=titledict)
    if ordered:
        if stacked:
            if percent==False:
                fig.update_layout(barmode='stack',xaxis={'categoryorder':'total ascending'})
            else:
                fig.update_layout(barmode='stack',xaxis={'categoryorder':'total ascending'})
        else:
            fig.update_layout(xaxis={'categoryorder':'total ascending'})
    else:
        if stacked:
            fig.update_layout(barmode='stack')
    if order2:
        fig.update_layout(xaxis={"categoryorder":"array","categoryarray":catorder})
    fig.update_layout(legend=dict(x=1.01, y=0))
    fig.update_layout(showlegend=show_legend)
    fig.update_layout(bargap = 0)
    fig.update_traces(marker_line_width=0)
    return fig

@app.route("/users/")
@flask_login.fresh_login_required
def view_users():
	users = User.query.all()
	return render_template("users.html", users=users)

@app.route("/users/active/<int:user_id>")
@flask_login.fresh_login_required
def active_user(user_id):
	user = User.query.get_or_404(user_id)
	user.active = True
	db.session.add(user)
	db.session.commit()
	flash("Admin activated.")
	return redirect(url_for("view_users"))

@app.route("/users/deactivate/<int:user_id>")
@flask_login.fresh_login_required
def deactivate_user(user_id):
	user = User.query.get_or_404(user_id)
	user.active = False
	db.session.add(user)
	db.session.commit()
	flash("Admin deactivated.")
	return redirect(url_for("view_users"))

@app.route("/users/delete/<int:user_id>")
@flask_login.fresh_login_required
def delete_user(user_id):
	user = User.query.get_or_404(user_id)
	db.session.delete(user)
	db.session.commit()
	flash("Admin deleted.")
	return redirect(url_for("view_users"))
