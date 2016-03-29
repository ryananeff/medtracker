from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from flask import flash

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
	formobj.survey.choices = [(survey.id, survey.title)]
	if request.method == 'POST' and formobj.validate():
		dbobj = Question(
				formobj.body.data,
				formobj.image.data,
				formobj.kind.data,
				survey_id
		)
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
	formout = QuestionForm(obj=question)
	formobj = QuestionForm(request.form)
        formout.survey_id.choices = [(survey.id, survey.title)]
	if request.method == 'POST' and formobj.validate():
		question.body = formobj.body.data
		question.image = formobj.image.data
		question.kind = formobj.kind.data
		question.survey_id = formobj.survey_id.data
		db_session.add(question)
		db_session.commit()
		flash('Question edited.')
		return redirect(url_for('view_survey', _id=survey_id))
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

@app.route('/questions/view/<int:_id>', methods=['GET', 'POST'])
#@flask_login.login_required
def view_question(_id):
    dbobj = Question.query.get_or_404(_id)
    return render_template("view_question.html", survey = dbobj)

### static files
	
@app.route('/assets/<path:path>')
def send_js(path):
    return send_from_directory('../assets', path)
