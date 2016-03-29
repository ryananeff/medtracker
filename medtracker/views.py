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

### controller functions

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
def edit_survey(survey_id):
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

### static files
	
@app.route('/assets/<path:path>')
def send_js(path):
    return send_from_directory('../assets', path)
