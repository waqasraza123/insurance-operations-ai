from insurance_operations.application import create_app
from insurance_operations.database.connection import create_database_engine
from insurance_operations.settings import ApiSettings
from insurance_operations.telephony.ingress import configure_twilio_ingress
from insurance_operations.telephony.settings import TelephonyProviderSettings

settings = ApiSettings()
database_engine = create_database_engine(
    settings,
    service_name="api",
)
app = create_app(settings, database_engine)

telephony_provider_settings = TelephonyProviderSettings()
configure_twilio_ingress(
    app,
    telephony_provider_settings,
    database_engine,
)
