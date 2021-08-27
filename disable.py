from medtracker import *
from medtracker import database
patients = models.Patient.query.all()
devices = models.Device.query.all()

kept = 0
discarded = 0
patients = models.Patient.query.all()
for p in patients:
    if p.deactivate==True:
        continue
    sr = [s.to_dict() for s in p.surveys]
    df = pd.DataFrame(sr)
    if len(df)>0:
        if any(df.start_time > datetime.date(2020,8,1)):
            kept += 1
            p.deactivate = False
            db.session.add(p)
        else:
            discarded += 1
            p.deactivate = True
            db.session.add(p)
    else:
        discarded += 1
        p.deactivate = True
        db.session.add(p)
db.session.commit()
print(kept,discarded)
