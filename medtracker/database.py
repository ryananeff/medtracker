from medtracker.config import *
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect

engine = create_engine(sqlalchemy_db, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import medtracker.models
    Base.metadata.create_all(bind=engine)
	
def query_to_dict(rset):
		result = dict()
		for obj in rset:
			instance = inspect(obj)
			for key, x in instance.attrs.items():
				if key in result:
					result[key].append(x.value)
				else:
					result[key] = [x.value]
		return result
