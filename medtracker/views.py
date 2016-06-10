from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from medtracker.email_helper import send_email
from medtracker.triggers import *
from flask import flash, Markup
import random, string
from werkzeug import secure_filename
import sys

from flask_login import login_user, logout_user, current_user

image_staticdir = '../assets/uploads/'

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
		user = User.query.filter_by(email=form.username.data).first_or_404()
		if user.active == False:
			msg = Markup('Please confirm your email to log in. <a href="/resend_confirmation?email=' + user.email + '">Resend Confirmation</a>')
			flash(msg)
		elif user.verify_password(form.password.data):
			login_user(user)
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
        send_email(user.email, subject, html)

        return redirect(url_for("login"))

    return render_template('form.html', form=form, action="Sign up for Suretify", data_type="")

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
def index():
	return render_template("index.html")

@app.route('/surveys', methods=['GET'])
@flask_login.login_required
def serve_survey_index():
	'''GUI: serve the survey index page'''
        surveys = current_user.surveys
        return render_template("surveys.html",
                                surveys = surveys)

@app.route('/responses', methods=['GET'])
@flask_login.login_required
def serve_responses_index():
	'''GUI: serve the response index page'''
	outdict = {}
	uniq_ids = [a.uniq_id for a in QuestionResponse.query.filter(QuestionResponse.user_id==current_user.id).group_by(QuestionResponse.uniq_id).all()]
	for u in uniq_ids:
		responses = QuestionResponse.query.filter(QuestionResponse.uniq_id==u)
		outdict[u] = responses
	return render_template("responses.html",
							responses = outdict)

@app.route('/triggers', methods=['GET'])
@flask_login.login_required
def serve_triggers_index():
	'''GUI: serve the trigger index page'''
        questions = Question.query.filter(Question.trigger_id != None, Trigger.user_id==current_user.id)
        triggers = Trigger.query.filter(Trigger.questions==None)
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
	if request.method == 'POST' and formobj.validate():
		survey.title = formobj.title.data
		survey.description = formobj.description.data
		db_session.add(survey)
		db_session.commit()
		flash('Survey edited.')
		return redirect(url_for('serve_survey_index'))
	return render_template("form.html", action="Edit", data_type="survey #" + str(_id), form=formout)

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
@flask_login.login_required
def start_survey(survey_id):
	uniq_id = randomword(64)
	survey = Survey.query.get_or_404(survey_id)
	return render_template('start_survey.html', survey=survey, u = uniq_id)
	#return redirect(url_for(serve_survey), survey_id=_id, u=uniq_id)

@app.route('/surveys/serve/<int:survey_id>', methods=['GET', 'POST'])
@flask_login.login_required
def serve_survey(survey_id):
	survey = Survey.query.get_or_404(survey_id)
	question_id = request.values.get("question", None)
	uniq_id = request.values.get("u", None)
	question_ids = [q.id for q in survey.questions]
	if len(question_ids) == 0:
			return render_template("view_survey.html", survey = survey)
	if question_id == None:
		question_id = question_ids[0]
	question_id = int(question_id)
	question = Question.query.get_or_404(question_id)
	curpos = question_ids.index(question_id)
	next_question = question_ids[curpos+1] if curpos+1 < len(question_ids) else None
	last_question = question_ids[curpos-1] if curpos-1 >= 0 else None
	formobj = QuestionView().get(question)
	if request.method == 'POST':
		if uniq_id:
			print "saving..."
			save_response(request.form, question_id)
		if next_question == None:
			return redirect(url_for('view_survey', _id=survey_id))
		return redirect(url_for('serve_survey', survey_id=survey_id, question=next_question, u=uniq_id))
	else:
		return render_template("serve_question.html", survey = survey, question = question, next_q = next_question, last_q = last_question, form=formobj, u=uniq_id)

def save_response(formdata, question_id, session_id=None):
	_response = QuestionResponse(
		formdata["response"],
		formdata["uniq_id"],
		session_id,
		question_id
	)
	_response.user_id = current_user.id
	db_session.add(_response)
	db_session.commit()
	question = _response._question
	if _response.uniq_id != None:
		sys.stderr.write('starting trigger')
		run_trigger(question, _response)
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
	if request.method == 'POST' and formout.validate():
		question.kind = formout.kind.data
		question.survey_id = formout.survey_id.data
		question.body = formout.body.data
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
	return render_template("form.html", action="Edit", data_type="question " + str(_id), form=formout)

@app.route('/questions/delete/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def remove_question(_id):
    dbobj = Question.query.get_or_404(_id)
    survey_id = dbobj.survey_id
    db_session.delete(dbobj)
    db_session.commit()
    flash('Question removed.')
    return redirect(url_for('view_survey', _id=survey_id))

### controller for trigger functions

@app.route('/triggers/new/', methods=['GET', 'POST'])
@flask_login.login_required
def add_trigger():
	'''GUI: add a trigger to the DB'''
	formobj = TriggerForm(request.form)
	formobj.questions.query = Question.query.filter(Survey.user_id==current_user.id).all()
	if request.method == 'POST' and formobj.validate():
		trigger = Trigger(
			formobj.title.data,
			formobj.kind.data,
			formobj.criteria.data,
			formobj.after_function.data
			)
		trigger.user_id = current_user.id
		db_session.add(trigger)
		db_session.commit()
		q = formobj.questions.data
		q.trigger_id = trigger.id
		db_session.add(q)
		db_session.commit()
		flash('Trigger added.')
		return redirect(url_for('serve_triggers_index'))
	#formobj.questions.choices = [(q.id, "(ID: %s) "% str(q.id) + q.body) for q in Question.query]
	return render_template("form.html", action="Add", data_type="a trigger", form=formobj)

@app.route('/triggers/edit/<int:_id>', methods=['GET', 'POST'])
@flask_login.login_required
def edit_trigger(_id):
	'''GUI: edit a trigger in the DB'''
	trigger = Trigger.query.get_or_404(_id)
	formout = TriggerForm(request.form, obj=trigger)
	formout.questions.query = Question.query.filter(Survey.user_id==current_user.id).all()
	if request.method == 'POST' and formout.validate():
		trigger.title = formout.title.data
		trigger.kind = formout.kind.data
		trigger.criteria = formout.criteria.data
		trigger.recipients = formout.recipients.data
		trigger.after_function = formout.after_function.data
		db_session.add(trigger)
		db_session.commit()
		for old_q in trigger.questions:
			old_q = Question.query.get(old_q.id)
			old_q.trigger_id = None
			db_session.add(old_q)
		q = formout.questions.data
		q.trigger_id = trigger.id
		db_session.add(q)
		db_session.commit()
		flash('Trigger edited.')
		return redirect(url_for('serve_triggers_index'))
	return render_template("form.html", action="Edit", data_type="trigger #" + str(_id), form=formout)

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
    db_session.delete(dbobj)
    db_session.commit()
    flash('Response removed.')
    return redirect(url_for('serve_responses_index'))

### static files (only when not running under Apache)
	
#@app.route('/assets/<path:path>')
#def send_js(path):
#    return send_from_directory('/var/wsgiapps/suretify/assets', path)

#### other helpers
    
def randomword(length):
	'''generate a random string of whatever length, good for filenames'''
	return ''.join(random.choice(string.lowercase) for i in range(length))
