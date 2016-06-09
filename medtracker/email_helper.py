# for sending emails out
from medtracker import *
from medtracker.models import *
from medtracker.forms import *
from flask.ext.mail import Message
from email.mime.text import MIMEText

def send_email(address, subject, html):
	'''send an email'''
	from_email = "info@suretify.co"
	msg = Message(sender=from_email)
	msg.sender  = from_email
	msg.recipients = [address]
	msg.subject = subject
	msg.html = html
	mail.send(msg)
	print "Sent email."
	return None