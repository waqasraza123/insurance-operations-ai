from insurance_operations.application import create_app
from insurance_operations.database.connection import create_database_engine
from insurance_operations.settings import ApiSettings

settings = ApiSettings()
database_engine = create_database_engine(settings, service_name="api")
app = create_app(settings, database_engine)
