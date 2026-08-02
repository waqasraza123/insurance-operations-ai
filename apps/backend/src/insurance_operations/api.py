from insurance_operations.application import create_app
from insurance_operations.settings import ApiSettings

app = create_app(ApiSettings())
