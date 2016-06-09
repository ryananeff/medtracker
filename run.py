import sys, os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from medtracker import app
app.run(debug=True)
