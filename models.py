from typing import Any

from pydantic import BaseModel


class TallyField(BaseModel):
    id: str
    label: str
    type: str
    value: Any  # str | bool | list[{name, url}] depending on field type


class TallyFormData(BaseModel):
    formId: str
    formName: str
    createdAt: str
    fields: list[TallyField]


class TallyWebhookPayload(BaseModel):
    data: TallyFormData
    eventType: str


class ParsedFormData(BaseModel):
    name: str
    role: str
    trust: str
    email: str
    consent: bool
    cv_url: str
    cv_filename: str
    person_spec_url: str
    person_spec_filename: str
