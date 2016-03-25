from medtracker import *
from medtracker.models import *

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

### static files
	
@app.route('/assets/<path:path>')
def send_js(path):
    return send_from_directory('../assets', path)
