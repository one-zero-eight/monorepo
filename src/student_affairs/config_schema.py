from pydantic import SecretStr

from src.config_primitives import BaseSchema, ServiceSettingsBase


class OmnideskSettings(BaseSchema):
    base_url: str = "https://student-affairs.omnidesk.ru"
    "URL in format: https://mydomain.omnidesk.ru"
    jwt_marker: SecretStr
    "JWT secret marker for user auth in Omnidesk. See instructions: https://support.omnidesk.ru/knowledge_base/item/54180"


class StudentAffairsSettings(ServiceSettingsBase):
    omnidesk: OmnideskSettings
    "Omnidesk integration settings"
