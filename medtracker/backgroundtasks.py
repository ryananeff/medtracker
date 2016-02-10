from medtracker import *
from medtracker.email_helper import *
from celery import Celery

def make_celery(app):
	'''pass flask to celery when background tasks are run'''
	celery = Celery(app.name)
	celery.config_from_object("celeryconfig")
	TaskBase = celery.Task
	class ContextTask(TaskBase):
		abstract = True
		def __call__(self, *args, **kwargs):
			with app.app_context():
				return TaskBase.__call__(self, *args, **kwargs)
	celery.Task = ContextTask
	return celery

#init celery
celery = make_celery(app)
