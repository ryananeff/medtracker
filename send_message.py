import os
os.chdir("/home/ubuntu/medtracker")
import datetime, pytz, time
from medtracker import *
already_sent = []
app.config["SERVER_NAME"]="ismmshealthcheck.com"
message="""ISMMS Student Health Check- There was an issue this morning preventing users from completing surveys due to a bad redirect after updating student records for the first time. The issue is resolved now."""
with app.app_context():
    pts = models.Patient.query.filter(models.Patient.phone.isnot("")).all()
    #today = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    #status = dict()
    #pts = [{"phone":""}]
    for p in pts:
        #ptstat = 0
        #taken = p.surveys.filter(SurveyResponse.end_time.isnot(None),SurveyResponse.start_time>today).order_by(SurveyResponse.id.desc()).first()
        #if taken!=None:
        #    if taken.completed:
        #        ptstat = 1
        #    if taken.exited:
        #        ptstat = -1 
        #if ptstat==0:
        if p.phone not in already_sent:
            print("sms_trigger(message,"+str(p.phone)+",None)")
            try:
                sms_trigger(message, p.phone,None)
            except:
                print("error in sending...")
            already_sent.append(p.phone)
            time.sleep(0.2)
