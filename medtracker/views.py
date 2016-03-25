from medtracker import *

@app.route("/", methods=['GET'])
def index():
	return render_template("index.html")
	
@app.route('/assets/<path:path>')
def send_js(path):
    return send_from_directory('../assets', path)
