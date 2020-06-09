from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
from medtracker.triggers import *

import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.dates as mdates
from plotly import offline
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go

image_staticdir = 'assets/uploads/'

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
			response.set_cookie('flashed',b'True',max_age=0)
			response.set_cookie('patient_ident', g.patient_ident, max_age=datetime.timedelta(weeks=52))
			device = Device(g.patient_ident)
			db.session.add(device)
			db.session.commit()
			g.device = device
			return response
	else:
		g.patient_ident = g.device.device_id
		g.patient = Patient.query.filter_by(mrn=g.patient_ident).first()

@app.after_request
def flash_warning(response):
	flashed = request.cookies.get('flashed',False)
	g.patient = Patient.query.filter_by(mrn=g.patient_ident).first()
	if (g.patient == None)&(flashed==False):
		flash("Your device appears to be unregistered. Please register your device.")
		response.set_cookie('flashed',b'True',max_age=0)
	return response	

#### logins

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view =  "login"

@login_manager.user_loader
def user_loader(user_id):				# used by Flask internally to load logged-in user from session
	return User.query.get(user_id)

@login_manager.unauthorized_handler
@app.route("/login", methods=["GET", "POST"])
def login():					# not logged-in callback
	form = UsernamePasswordForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.username.data).first()
		if user == None:
			return str("Error: '" + form.username.data + "'")
		if user.active == False:
			msg = Markup('Please confirm your email to log in. <a href="/resend_confirmation?email=' + user.email + '">Resend Confirmation</a>')
			flash(msg)
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
        user = User(
            email = form.email.data,
            username = form.username.data,
            name = form.name.data,
        )
        user.hash_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # Now we'll send the email confirmation link
        subject = "Confirm your email"

        token = ts.dumps(user.email, salt='email-confirm-key')

        confirm_url = url_for(
            'confirm_email',
            token=token,
            _external=True)

        html = render_template(
            'activate_user_by_email.html',
            confirm_url=confirm_url)

        # We'll assume that send_email has been defined in myapp/util.py
        #send_email(user.email, subject, html)

        return redirect(url_for("login"))

    return render_template('form_signup.html', form=form, action="Sign up for Suretify", data_type="")

@app.route('/resend_confirmation', methods=["GET", "POST"])
def resend_confirmation():
	email = request.values.get('email', None)

	user = User.query.filter_by(email=email).first_or_404()
	if user.active == True:
		flash('Email address already confirmed, please try signing in again.')
		return redirect(url_for("login"))

	# Now we'll send the email confirmation link
	subject = "Confirm your email"

	token = ts.dumps(user.email, salt='email-confirm-key')

	confirm_url = url_for(
	    'confirm_email',
	    token=token,
	    _external=True)

	html = render_template(
	    'activate_user_by_email.html',
	    confirm_url=confirm_url)

	# We'll assume that send_email has been defined in myapp/util.py
	send_email(user.email, subject, html)
	flash("Sent you a confirmation email.")
	return redirect(url_for("login"))

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = ts.loads(token, salt="email-confirm-key", max_age=86400)
    except:
        abort(404)

    user = User.query.filter_by(email=email).first_or_404()

    user.active = True

    db.session.add(user)
    db.session.commit()
    flash("Your email address has been successfully confirmed.")
    return redirect(url_for('login'))

#### index pages

@app.route("/", methods=['GET'])
@app.route("/index.html", methods=['GET'])
def index():
	return render_template("index.html")

@app.route("/about", methods=["GET"])
def about():
	return render_template("about.html")

@app.route('/surveys', methods=['GET'])
@flask_login.login_required
def serve_survey_index():
	'''GUI: serve the survey index page'''
	surveys = current_user.surveys
	for s in surveys:
		try:
			s.description_html = delta_html.render(json.loads(s.description)["ops"])
		except:
			s.description_html = '<p>' + s.description + '</p>'
	return render_template("surveys.html",
	                        surveys = surveys)

@app.route('/responses', methods=['GET'])
@flask_login.login_required
def serve_responses_index():
	'''GUI: serve the response index page'''
	responses = current_user.responses
	return render_template("responses.html",
							responses = responses)

@app.route('/triggers', methods=['GET'])
@flask_login.login_required
def serve_triggers_index():
	'''GUI: serve the trigger index page'''
	triggers = Trigger.query.filter(Trigger.questions==None, Trigger.user_id==current_user.id)
	questions = Question.query.filter(Question.trigger_id != None, Trigger.user_id==current_user.id)
	return render_template("triggers.html",
		questions = questions, 
		triggers = triggers)                         

### controller functions for surveys

@app.route('/surveys/new/', methods=['GET', 'POST'])
@flask_login.login_required
def add_survey():
	'''GUI: add a survey to the DB'''
	formobj = SurveyForm(request.form)
	if request.method == 'POST' and formobj.validate():
		dbobj = Survey(formobj.title.data, formobj.description.data)
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
	return render_template("form.html", action="Edit", data_type="survey #" + str(_id), form=formout)

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
    triggers = dict()
    for question in dbobj.questions():
    	if question.triggers != None:
    		tlist=[]
    		for trigger in question.triggers:
	    		after = Survey.query.get(trigger.after_function) if trigger.after_function else None
	    		tlist.append((trigger, after))
	    	triggers[question.id] = tlist
    return render_template("view_survey.html", survey = dbobj, triggers = triggers)

@app.route('/surveys/start/<int:survey_id>', methods=['GET', 'POST'])
def start_survey(survey_id):
	'''TODO: need to select the patient which will be taking the survey. This will make this starting block a form.'''
	if g.patient == None:
		return redirect(url_for('patient_signup',survey_id=survey_id))
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
	survey_response_id = request.values.get("sr", None)
	question_id = request.values.get("question", None)
	uniq_id = request.values.get("u", None)
	sess = request.values.get("s", None)

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
	if request.method == 'POST':
		if uniq_id:
			print("saving...")
			trigger_survey = save_response(request.form, question_id, session_id = sess, survey_response_id = survey_response.id)
			if trigger_survey != None:
				return redirect(url_for('start_survey', survey_id=trigger_survey, u=uniq_id, s = sess))
		if next_question == None:
			survey_response.complete()
			db_session.add(survey_response)
			db_session.commit()
			return redirect(url_for("complete_survey", session_id=survey_response.session_id))
		return redirect(url_for('serve_survey', survey_id=survey_id, question=next_question, u=uniq_id, s=sess, sr = survey_response.id))
	else:
		try:
			question.description_html = delta_html.render(json.loads(question.description)["ops"])
		except:
			question.description_html = '<p>' + question.description + '</p>'
		return render_template("serve_question.html", survey = survey, question = question, 
		                       next_q = next_question, last_q = last_question, form=formobj, u=uniq_id, s = sess, sr = survey_response.id)

@app.route("/cr/<session_id>")
def complete_survey(session_id):
	record = SurveyResponse.query.filter_by(session_id=session_id).first()
	if record==None:
		return "Completion record not found.",404
	survey = record.survey
	if current_user.is_authenticated:
		if record.completed:
			patient = record.patient
			end_time = record.end_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/New_York'))
			day_num = end_time.timetuple().tm_yday % 46+1
			img_path = os.path.join(os.getcwd(),'assets/images/animals/animal%d.jpg'%day_num)
			qrcode_out = qrcode(url_for('complete_survey',session_id=record.session_id,_external=True),error_correction='Q',icon_img=img_path)
			return render_template("survey_complete.html",record=record, patient = patient,survey=survey,qrcode_out=qrcode_out)
		else:
			return "Completion record not found.",404
	if g.patient:
		if record.uniq_id != g.patient.id:
			return "Your device isn't authorized to view this completion record.", 401
		else:
			if record.completed:
				end_time = record.end_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/New_York'))
				day_num = end_time.timetuple().tm_yday % 46+1
				img_path = os.path.join(os.getcwd(),'assets/images/animals/animal%d.jpg'%day_num)
				qrcode_out = qrcode(url_for('complete_survey',session_id=record.session_id,_external=True),error_correction='Q',icon_img=img_path)
				return render_template("survey_complete.html",record=record, patient = g.patient,survey=survey,qrcode_out=qrcode_out)
			else:
				return "Completion record not found.",404
	else:
		return "Your device appears to be unregistered. Only registered devices can view completion records.",401

def save_response(formdata, question_id, session_id=None, current_user = None, survey_response_id = None):
	question = Question.query.get_or_404(question_id)
	survey_response = SurveyResponse.query.get_or_404(survey_response_id)
	_response = QuestionResponse(
		formdata.getlist("response"),
		formdata["uniq_id"],
		session_id,
		question_id, 
		survey_response_id
	)
	if (question.kind =="select") | (question.kind=="radio" ):
			try:
				choices = json.loads(question.choices)
				for ix,r in enumerate(_response.response):
					_response.response[ix] = choices[r]
			except:
				print("ERROR: can't convert response ID to choice")
				pass
	_response.response = _response.response[0] if len(_response.response)==1 else _response.response
	print(_response.response)
	_response.user_id = Patient.query.get(formdata["uniq_id"]).user_id
	db_session.add(_response)
	db_session.commit()
	question = _response._question
	if _response.uniq_id != None:
		sys.stderr.write('starting trigger')
		return run_trigger(question, _response, "web", session_id, current_user)
	return "Response saved."

### controller functions for questions

@app.route('/questions/new/', methods=['GET', 'POST'])
@flask_login.login_required
def add_question():
	'''GUI: add a question to a survey'''
	_id = request.values.get("survey", None)
	if _id == None:
		return "could not find survey", 404
	survey = Survey.query.get_or_404(_id)
	survey_id = survey.id
	formobj = QuestionForm(request.form, survey_id=survey_id)
	formobj.survey_id.choices = [(s.id, s.title) for s in Survey.query]
	formobj.survey_id.data = survey.id
	if request.method == 'POST' and formobj.validate():
		dbobj = Question(
				formobj.body.data,
				formobj.description.data,
				formobj.choices.data,
				None,
				formobj.kind.data,
				formobj.survey_id.data
		)
		dbobj.user_id = current_user.id
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
		flash("""You have registered this device and browser to take the COVID-19 screening.\n
		      You will need to use this same device and browser to submit future screenings and show compliance.\n
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
	patient = Patient.query.filter_by(user_id=current_user.id, mrn=id).first_or_404()
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
	return render_template("form.html", action="Edit", data_type="patient", form=formobj)

@app.route("/patients/")
def view_patients():
	patients = current_user.patients
	status = dict()
	for p in patients:
		incomplete = sum([1-i.complete for i in p.progress])
		status[p.id] = incomplete
	return render_template("patients.html", patients=patients, status = status)

@app.route("/patients/delete/<string:id>")
def delete_patient(id):
	patient = Patient.query.filter_by(mrn=id).first_or_404()
	db_session.delete(patient)
	db_session.commit()
	flash('Patient deleted.')
	return redirect(url_for('view_patients'))

@app.route('/patients/<int:id>/give_survey', methods=['GET'])
def patient_survey_selector(id):
	'''GUI: serve the survey select page for a patient'''
	patient = Patient.query.get_or_404(id)
	surveys = patient.user.surveys
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
	if q:
		question = Question.query.get(q)
	if question:
		formobj.question_id.query = [question]
	else:
		formobj.question_id.query = Question.query.filter(Survey.user_id==current_user.id).all()
	formobj.after_function.query = Survey.query.filter_by(user_id=current_user.id).all()
	if request.method == 'POST' and formobj.validate():
		if formobj.after_function.data:
			af = formobj.after_function.data.id
		else:
			af = None
		trigger = Trigger(
			formobj.title.data,
			formobj.kind.data,
			formobj.criteria.data,
			formobj.recipients.data,
			af
			)
		trigger.user_id = current_user.id
		trigger.question_id = formobj.question_id.data.id
		db_session.add(trigger)
		db_session.commit()
		flash('Trigger added.')
		if question:
			return redirect(url_for('view_survey', _id=question.survey.id))
		else:
			return redirect(url_for('serve_survey_index'))
	#formobj.questions.choices = [(q.id, "(ID: %s) "% str(q.id) + q.body) for q in Question.query]
	return render_template("form_trigger.html", action="Add", data_type="a trigger", form=formobj)

@app.route('/triggers/edit/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_trigger(_id):
	'''GUI: edit a trigger in the DB'''
	trigger = Trigger.query.get_or_404(_id)
	formout = TriggerForm(request.form, obj=trigger)
	formout.question_id.query = Question.query.filter(Survey.user_id==current_user.id).all()
	formout.after_function.query = Survey.query.filter_by(user_id=current_user.id).all()
	if request.method == 'POST' and formout.validate():
		if formout.after_function.data:
			af = formout.after_function.data.id
		else:
			af = None
		trigger.title = formout.title.data
		trigger.kind = formout.kind.data
		trigger.criteria = formout.criteria.data
		trigger.recipients = formout.recipients.data
		trigger.after_function = af
		trigger.question_id = formout.question_id.data.id
		db_session.add(trigger)
		db_session.commit()
		flash('Trigger edited.')
		return redirect(url_for('view_survey', _id=Question.query.get(trigger.question_id).survey.id))
	else:
		formout.kind.data = trigger.kind
		formout.question_id.data = Question.query.get(trigger.question_id)
		if trigger.after_function:
			formout.after_function.data = Survey.query.get(trigger.after_function)
	return render_template("form_trigger.html", action="Edit", data_type="trigger #" + str(_id), form=formout)

@app.route('/triggers/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_trigger(_id):
    dbobj = Trigger.query.get_or_404(_id)
    db_session.delete(dbobj)
    db_session.commit()
    flash('Trigger removed.')
    return redirect(url_for('serve_triggers_index'))
    
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
    return send_from_directory('/Users/ryanneff/suretify/medtracker/assets', path)

@app.route('/patient_feed/', methods=["GET", "POST"])
@app.route('/patient_feed/<int:id>/', methods=["GET", "POST"])
@flask_login.login_required
def patient_feed(id=None):
	if id:
		patients = Patient.query.filter_by(id=id, user_id=current_user.id)
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
	p = Patient.query.filter_by(id=id, user_id=current_user.id).first()
	patients_feed = []
	for s in p.surveys:
		patients_feed.append((s.start_time.strftime("%Y-%m-%d %H:%M:%S"),"patient", s))
	comments = Comment.query.filter_by(patient_id=p.id)
	for c in comments:
		patients_feed.append((c.time.strftime("%Y-%m-%d %H:%M:%S"), "comment", c))
	patients_feed = sorted(patients_feed, key=lambda x:x[0],reverse=False)
	status = sum([1-i.complete for i in p.progress])
	return render_template('view_patient.html', patients_feed = patients_feed, patient=p, status=status)

@app.route('/patients/self', methods=["GET", "POST"])
def view_patient_self():
	if g.patient == None:
		return "Please register your device first, then come back to this page.", 404
	p = g.patient
	patients_feed = []
	for s in p.surveys:
		patients_feed.append((s.start_time.strftime("%Y-%m-%d %H:%M:%S"),"patient", s))
	patients_feed = sorted(patients_feed, key=lambda x:x[0],reverse=True)
	status = sum([1-i.complete for i in p.progress])
	return render_template('view_patient_self.html', patients_feed = patients_feed, patient=p, status=status)

@app.route('/comment/add/<int:patient_id>/', methods=["GET", "POST"])
@flask_login.login_required
def add_comment(patient_id):
	user_id = current_user.id
	if patient_id not in [i.id for i in current_user.patients]:
		return "Not Found", 404
	if request.method == 'POST':
		body = request.form["body"] if request.form["body"] != "" else None
	if body:
		comment = Comment(body, patient_id, user_id)
		db_session.add(comment)
		db_session.commit()
		return redirect(url_for('view_patient', id=patient_id))
	else:
		return "Failure.", 400

@app.route('/comment/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_comment(_id):
    dbobj = Comment.query.get_or_404(_id)
    patient_id = dbobj.patient_id
    db_session.delete(dbobj)
    db_session.commit()
    flash('Comment removed.')
    return redirect(url_for('view_patient', id=patient_id))

@app.route("/test",methods=["GET"])
@flask_login.login_required
def test_plotly():
	patients = models.Patient.query.all()
	devices = models.Device.query.all()

	def model_to_pd(model):
	    res = [r.to_dict() for r in model.query.all()]
	    return pd.DataFrame(res)

	sres = []
	for p in patients:
	    sr = [s.to_dict() for s in p.surveys.all()]
	    sres.extend(sr)

	sres = pd.DataFrame(sres)
	sres["date"] = sres.end_time.dt.floor('d')
	sres = sres.groupby(["date","uniq_id"]).first()
	sres = sres.reset_index()

	devs = pts = model_to_pd(models.Device)
	devs_per_day = pd.DataFrame(devs.groupby([devs.creation_time.dt.floor("d")])["creation_time"].count())
	devs_per_day.columns = ["daily_new_devices"]
	pts = model_to_pd(models.Patient)
	pts_per_day = pd.DataFrame(pts.groupby([pts.creation_time.dt.floor("d")])["creation_time"].count())
	pts_per_day.columns = ["daily_registered_students"]
	res_per_day = pd.DataFrame(sres.groupby([sres.end_time.dt.floor('d')])["end_time"].count())
	res_per_day.columns = ["daily_completed_surveys"]
	df = pd.merge(pts_per_day,res_per_day,left_index=True,right_index=True,how="outer")
	df = pd.merge(df,devs_per_day,left_index=True,right_index=True,how="outer")
	begin_time = datetime.datetime.now().date() - datetime.timedelta(days=14)
	df = df.reindex(pd.date_range(begin_time, datetime.datetime.now().date())).fillna(0).astype(int)
	df["total_registered_students"] = df["daily_registered_students"].cumsum()
	df["total_completed_surveys"] = df["daily_registered_students"].cumsum()
	df["total_devices"] = df["daily_new_devices"].cumsum()
	df.reset_index(inplace=True)
	df = df.sort_values(by="index",ascending=True)
	df["index"] = [datetime.datetime.strftime(a,"%D") for a in df["index"]]
	fig1 = plotlyBarplot(data=df,x="index",y="total_devices",width=400,height=300,title="Total Devices Seen")
	fig2 = plotlyBarplot(data=df,x="index",y="total_registered_students",width=400,height=300,title="Total Registered Students")
	df["daily_uncompleted_surveys"] = df["total_registered_students"] - df["daily_completed_surveys"]
	df["daily_pct"] = df["daily_completed_surveys"]/df["total_registered_students"]*100
	df2 = df.loc[:,["index","daily_uncompleted_surveys","daily_completed_surveys"]]
	df2.columns = ["index","Not Completed","Completed"]
	df3 = df2.melt(id_vars="index")
	fig3 = plotlyBarplot(data=df3,x="index",y="value",hue="variable",width=400,height=300, title="Screening Status",stacked=True)
	fig1 = offline.plot(fig1,show_link=False, output_type="div", include_plotlyjs=False)
	fig2 = offline.plot(fig2,show_link=False, output_type="div", include_plotlyjs=False)
	fig3 = offline.plot(fig3,show_link=False, output_type="div", include_plotlyjs=False)
	patient_count = len(patients)
	device_count = len(devices)
	today_count = list(df["daily_completed_surveys"])[-1]
	today_pct = list(df["daily_pct"])[-1]
	week_count = sum(list(df["daily_completed_surveys"])[-7:])
	week_pct = sum(list(df["daily_completed_surveys"])[-7:])/sum(list(df["total_registered_students"])[-7:])*100
	return render_template("dashboard.html",fig1=fig1,fig2=fig2,fig3=fig3,patient_count=patient_count,device_count=device_count,
	                       today_count=today_count, today_pct=today_pct, week_count=week_count, week_pct=week_pct)

def plotlyBarplot(x=None,y=None,hue=None,data=None,ylabel="",xlabel="",title="",
                    width=600,height=400,colors=["rgba"+str(i) for i in cm.get_cmap("Dark2").colors],
                    stacked=False,percent=False,ordered=False):
    yaxis=go.layout.YAxis(
            title=ylabel,
            automargin=True,
            titlefont=dict(size=12),
        )

    xaxis=go.layout.XAxis(
            title=xlabel,
            automargin=True,
            titlefont=dict(size=12),
            type='category'
        )

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
    ylab = y
    xlab = x
    
    ix = 0
    if hue != None:
        data = data[[type(i)!=float for i in data[hue]]]
        if percent:
            totalcounts = data.groupby(xlab).sum()[ylab]
        for hue,group in data.groupby(hue):
            counts = group.groupby(xlab).sum()[ylab]
            if percent:
                counts = round(counts/totalcounts.loc[counts.index,]*100,1)
            x = [str(i) for i in counts.index]
            y = counts.values
            trace = go.Bar(x=x,y=y,
                           text=y,
                           textposition='auto',
                           orientation='v',
                         marker=dict(color=colors[ix]),
                         name="%s"%(hue))
            ix += 1
            fig.add_trace(trace)
    else:
        counts = data.groupby(xlab).sum()[ylab]
        x = [str(i) for i in counts.index]
        y = counts.values
        trace = go.Bar(x=x,y=y,
                       text=y,
                       textposition='auto',
                       orientation='v',
                     marker=dict(color=colors[ix]),
                     name="%s"%(ylabel))
        ix += 1
        fig.add_trace(trace)
    fig.update_layout(title=titledict)
    if ordered:
        if stacked:
            if percent==False:
                fig.update_layout(barmode='stack',xaxis={'categoryorder':'total ascending'})
            else:
                fig.update_layout(barmode='stack',xaxis={'categoryorder':'category descending'})
        else:
            fig.update_layout(xaxis={'categoryorder':'total ascending'})
    else:
        if stacked:
            fig.update_layout(barmode='stack')
    fig.update_layout(margin=dict(l=10, r=10, t=60, b=10,pad=0),showlegend=False)
    return fig