from models import ParsedFormData, TallyWebhookPayload


def extract_fields(payload: TallyWebhookPayload) -> ParsedFormData:
    """Map Tally webhook fields to structured form data by label matching.

    Tally sends FILE_UPLOAD fields as: [{"name": "...", "url": "...", "mimeType": "...", ...}]
    CHECKBOXES fields arrive as either an array of selected option IDs or a boolean.
    Fields with a null label (e.g. the raw checkbox group) are skipped.
    """
    data: dict = {}

    for field in payload.data.fields:
        if field.label is None:
            continue

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
            data["person_spec_mimetype"] = file_entry["mimeType"]

        elif "cv" in label:
            file_entry = field.value[0]
            data["cv_url"] = file_entry["url"]
            data["cv_filename"] = file_entry["name"]

        elif "email" in label:
            data["email"] = field.value

        elif "consent" in label:
            data["consent"] = bool(field.value)

    return ParsedFormData(**data)
