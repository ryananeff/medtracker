import os
os.chdir("/home/ubuntu/medtracker")
import datetime, pytz, time
from medtracker import *
already_sent = []
app.config["SERVER_NAME"]="ismmshealthcheck.com"
with app.app_context():
    pts = models.Patient.query.filter(models.Patient.phone.isnot("")).all()
    today = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    status = dict()
    for p in pts:
        ptstat = 0
        taken = p.surveys.filter(SurveyResponse.end_time.isnot(None),SurveyResponse.start_time>today).order_by(SurveyResponse.id.desc()).first()
        if taken!=None:
            if taken.completed:
                ptstat = 1
            if taken.exited:
                ptstat = -1 
        if ptstat==0:
            if p.phone not in already_sent:
                print("remind_sms(1,"+str(p.id)+")")
                try:
                    remind_sms(1,p.id)
                except:
                    print("error in sending...")
                already_sent.append(p.phone)
            time.sleep(0.2)
