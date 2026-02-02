from typing import Any

from pydantic import BaseModel, ConfigDict


class TallyField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    label: str | None
    type: str
    value: Any
    options: list[dict[str, Any]] | None = None


class TallyFormData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    formId: str
    formName: str
    createdAt: str
    fields: list[TallyField]


class TallyWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: TallyFormData


class ParsedFormData(BaseModel):
    name: str
    role: str
    trust: str = "Not specified"
    email: str
    consent: bool
    cv_url: str
    cv_filename: str
    person_spec_url: str
    person_spec_mimetype: str
