from models import ParsedFormData, TallyWebhookPayload


def extract_fields(payload: TallyWebhookPayload) -> ParsedFormData:
    """Map Tally webhook fields to structured form data by label matching.

    Tally sends file fields as: [{"name": "filename.ext", "url": "https://..."}]
    Checkbox fields arrive as a boolean value.
    """
    data: dict = {}

    for field in payload.data.fields:
        label = field.label.strip().lower()

        if "full name" in label:
            data["name"] = field.value

        elif "nhs role" in label:
            data["role"] = field.value

        elif "nhs trust" in label:
            data["trust"] = field.value

        elif "person specification" in label:
            file_entry = field.value[0]
            data["person_spec_url"] = file_entry["url"]
            data["person_spec_filename"] = file_entry["name"]

        elif "cv" in label:
            file_entry = field.value[0]
            data["cv_url"] = file_entry["url"]
            data["cv_filename"] = file_entry["name"]

        elif "email" in label:
            data["email"] = field.value

        elif "consent" in label:
            data["consent"] = bool(field.value)

    return ParsedFormData(**data)
