from medtracker import *
from sqlalchemy import func, desc
import pandas as pd

dbobj = models.SurveyResponse.query.all()

objects = pd.DataFrame([i.to_dict() for i in dbobj])
delete_count = 0
to_delete = set()
for name,group in objects.groupby("session_id"):
	if len(group)>1:
		group = group.sort_values("start_time",ascending=False)
		print(group)
		successful = group[(group["completed"]==1)|(group["exited"]==1)]
		if len(successful)>0:
			keep_id = group[(group["completed"]==1)|(group["exited"]==1)].iloc[0,].name
			print("keeping ID:", keep_id)
		else:
			keep_id = None
		for ix,row in group.iterrows():
			if row.name==keep_id: continue
			print("deleting ID: ",row.name)
			to_delete.add(row.name)
			delete_count += 1
	else:
		row = group.iloc[0,]
		if (row["completed"]==False) & (row["exited"]==False):
			print("deleting ID: ",row.name)
			to_delete.add(row.name)
			delete_count += 1

delete_objs = [dbobj[i] for i in to_delete]