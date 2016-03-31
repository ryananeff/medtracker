from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from flask import flash
import random, string
from werkzeug import secure_filename

image_staticdir = '../assets/uploads/'

#### index pages

@app.route("/", methods=['GET'])
def index():
	return render_template("index.html")

@app.route('/surveys', methods=['GET'])
##@flask_login.login_required
def serve_survey_index():
	'''GUI: serve the survey index page'''
        surveys = Survey.query
        return render_template("surveys.html",
                                surveys = surveys)

@app.route('/responses', methods=['GET'])
##@flask_login.login_required
def serve_responses_index():
	'''GUI: serve the response index page'''
        responses = QuestionResponse.query
        return render_template("responses.html",
                                responses = responses)

@app.route('/triggers', methods=['GET'])
##@flask_login.login_required
def serve_triggers_index():
	'''GUI: serve the trigger index page'''
        triggers = Trigger.query
        return render_template("triggers.html",
                                triggers = triggers)                         

### controller functions for surveys

@app.route('/surveys/new/', methods=['GET', 'POST'])
#@flask_login.login_required
def add_survey():
	'''GUI: add a survey to the DB'''
	formobj = SurveyForm(request.form)
	if request.method == 'POST' and formobj.validate():
		dbobj = Survey(formobj.title.data)
		db_session.add(dbobj)
		db_session.commit()
		flash('Survey added.')
		return redirect(url_for('serve_survey_index'))
	return render_template("form.html", action="Add", data_type="a survey", form=formobj)

@app.route('/surveys/edit/<int:_id>', methods=['GET', 'POST'])
#@flask_login.login_required
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
#@flask_login.login_required
def remove_survey(_id):
    dbobj = Survey.query.get_or_404(_id)
    db_session.delete(dbobj)
    db_session.commit()
    flash('Survey removed.')
    return redirect(url_for('serve_survey_index'))

@app.route('/surveys/view/<int:_id>', methods=['GET', 'POST'])
#@flask_login.login_required
def view_survey(_id):
    dbobj = Survey.query.get_or_404(_id)
    return render_template("view_survey.html", survey = dbobj)

@app.route('/surveys/start/<int:survey_id>', methods=['GET', 'POST'])
def start_survey(survey_id):
	uniq_id = randomword(64)
	survey = Survey.query.get_or_404(survey_id)
	return render_template('start_survey.html', survey=survey, u = uniq_id)
	#return redirect(url_for(serve_survey), survey_id=_id, u=uniq_id)

@app.route('/surveys/serve/<int:survey_id>', methods=['GET', 'POST'])
#@flask_login.login_required
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
	db_session.add(_response)
	db_session.commit()
	return "Response saved."

### controller functions for questions

@app.route('/questions/new/', methods=['GET', 'POST'])
#@flask_login.login_required
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
#@flask_login.login_required
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
#@flask_login.login_required
def remove_question(_id):
    dbobj = Question.query.get_or_404(_id)
    survey_id = dbobj.survey_id
    db_session.delete(dbobj)
    db_session.commit()
    flash('Question removed.')
    return redirect(url_for('view_survey', _id=survey_id))

### controller for trigger functions

@app.route('/triggers/new/', methods=['GET', 'POST'])
#@flask_login.login_required
def add_trigger():
	'''GUI: add a trigger to the DB'''
	formobj = TriggerForm(request.form)
	if request.method == 'POST' and formobj.validate():
		trigger = Trigger(
			formobj.title.data,
			formobj.kind.data,
			formobj.criteria.data,
			formobj.after_function.data
			)
		db_session.add(trigger)
		q = Question.query.get_or_404(formobj.questions.data.id)
		q.trigger_id = trigger.id
		db_session.add(q)
		db_session.commit()
		flash('Trigger added.')
		return redirect(url_for('serve_triggers_index'))
	#formobj.questions.choices = [(q.id, "(ID: %s) "% str(q.id) + q.body) for q in Question.query]
	return render_template("form.html", action="Add", data_type="a trigger", form=formobj)

@app.route('/triggers/edit/<int:_id>', methods=['GET', 'POST'])
#@flask_login.login_required
def edit_trigger(_id):
	'''GUI: edit a trigger in the DB'''
	trigger = Trigger.query.get_or_404(_id)
	formout = TriggerForm(obj=trigger)
	formobj = TriggerForm(request.form)
	if request.method == 'POST' and formobj.validate():
		trigger.title = formobj.title.data
		trigger.kind = formobj.kind.data
		trigger.criteria = formobj.criteria.data
		trigger.after_function = formobj.after_function.data
		db_session.add(trigger)
		for old_q in trigger.questions:
			old_q = Question.query.get(old_q.id)
			old_q.trigger_id = None
			db_session.add(old_q)
		q = Question.query.get_or_404(formobj.questions.data.id)
		q.trigger_id = trigger.id
		db_session.add(q)
		db_session.commit()
		flash('Trigger edited.')
		return redirect(url_for('serve_triggers_index'))
	return render_template("form.html", action="Edit", data_type="trigger #" + str(_id), form=formout)

@app.route('/triggers/delete/<int:_id>', methods=['GET', 'POST'])
#@flask_login.login_required
def remove_trigger(_id):
    dbobj = Trigger.query.get_or_404(_id)
    db_session.delete(dbobj)
    db_session.commit()
    flash('Trigger removed.')
    return redirect(url_for('serve_triggers_index'))

### static files
	
@app.route('/assets/<path:path>')
def send_js(path):
    return send_from_directory('../assets', path)

#### other helpers
    
def randomword(length):
	'''generate a random string of whatever length, good for filenames'''
	return ''.join(random.choice(string.lowercase) for i in range(length))
