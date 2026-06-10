from src.common_config import ServiceSettingsBase


class When2MeetSettings(ServiceSettingsBase):
    service_name: str = "when2meet"
    "Human-readable service name returned by the health endpoint"
