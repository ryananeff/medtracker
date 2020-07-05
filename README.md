# ISMMS Student Health Check
<img src="https://github.com/nosarcasm/medtracker/blob/master/assets/images/suretify-logo.png?raw=true" height=100 />

COVID-19 tracking app, and more!

## Installation

```bash
~/medtracker $ pip install pipenv
~/medtracker $ pipenv install
~/medtracker $ cp medtracker/config.py.example medtracker/config.py
```

This will set up a minimal configuration which uses a SQLite database located in the `medtracker` directory.

## Testing

Because of how `pytest` handles the Python path, we run into a
`ModuleNotFoundError` when trying to run `pytest` from the root directory.
`run_tests.sh` sets the Python path properly before calling `pytest`.

```bash
~/medtracker $ ./run_tests.sh
```

## Updates

News:
Release 1.0 is around the corner! Woo hoo!

Recent-er News: 
* Editing survey doesn't work (fixed)
* Questions don't have body description text (fixed)
* Questions don't have radio select or checkbox select (fixed!)
* Question editor doesn't have an intuitive way to add options (fixed!)
* Each survey session should be logged in a DB as a separate table (fixed!)
* Questions should support a next and previous option like a doubly linked list (done!)
* Can't reorder questions in a survey (fixed!)
* Question description doesn't support HTML (fixed!)
* Make student-facing version of the webpage that includes the auth mechanism we want (fixed)
* Student-facing version should be able to be taken anonymously and have an on-boarding process (fixed)
* Need to be able to generate some sort of code saying the person took the survey (fixed)
* Survey/question view needs to be improved (fixed)

Older News:
* 2/10/2016: This is just a skeleton at the moment. It won't be able to run.
* 3/25/2016: Runable skeleton with models made and index pages for views (but the controller needs to be built).
* 4/10/2016: Runable demo with surveys, triggers, responses (but only survey data collection working).
* 6/10/2016: Triggers working to SMS, email, phone, and URLs (but no trigger data collection yet).
* 7/23/2016: You can now take surveys by SMS and phone (as well as email of course as always).
* 7/23/2016: Autocomplete now works!

<img src="https://github.com/nosarcasm/medtracker/blob/master/examples/autocomplete.PNG?raw=true" height=500 />

* 9/22/2016: Editor view improvements, patients table, and layout improvements to the forms are up

<img src="https://github.com/nosarcasm/medtracker/blob/master/examples/editor_view.PNG?raw=true" height=500 />

* 9/23/2016: New dashboard layout, patient view, so much success!

<img src="https://github.com/nosarcasm/medtracker/blob/master/examples/survey_editor.PNG?raw=true" height=500 />

<img src="https://github.com/nosarcasm/medtracker/blob/master/examples/patient_view.PNG?raw=true" height=400 />

<img src="https://github.com/nosarcasm/medtracker/blob/master/examples/trigger_edit.PNG?raw=true" height=500 />
