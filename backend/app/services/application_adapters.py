from abc import ABC, abstractmethod
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger("jobhunter")

class BaseApplicationAdapter(ABC):
    """
    Abstract base class for platform-specific application adapters (Greenhouse, Lever, Workday, Generic).
    """

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        pass

    @abstractmethod
    def extract_fields(self, html_content: str) -> List[Dict[str, Any]]:
        pass


class GenericApplicationAdapter(BaseApplicationAdapter):
    """
    Generic application adapter that parses standard HTML form inputs or provides standard application form structure.
    """

    def can_handle(self, url: str) -> bool:
        return True  # Fallback adapter for any application URL

    def extract_fields(self, html_content: str) -> List[Dict[str, Any]]:
        fields = []
        if not html_content or len(html_content.strip()) < 10:
            return self._get_default_form_fields()

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            inputs = soup.find_all(["input", "textarea", "select"])

            for idx, elem in enumerate(inputs):
                elem_type = elem.name
                input_type = elem.get("type", "text").lower() if elem_type == "input" else elem_type

                if input_type in ["hidden", "submit", "button", "image"]:
                    continue

                field_name = elem.get("name") or elem.get("id") or f"field_{idx+1}"
                required = elem.get("required") is not None or elem.get("aria-required") == "true"

                # Find associated label text
                label_text = ""
                if elem.get("id"):
                    label_elem = soup.find("label", attrs={"for": elem.get("id")})
                    if label_elem:
                        label_text = label_elem.get_text(strip=True)

                if not label_text and elem.parent and elem.parent.name == "label":
                    label_text = elem.parent.get_text(strip=True)

                if not label_text:
                    label_text = elem.get("placeholder") or field_name.replace("_", " ").title()

                # Map HTML input types to internal field_type
                field_type = "TEXT"
                if input_type in ["email"]:
                    field_type = "EMAIL"
                elif input_type in ["tel", "phone"]:
                    field_type = "PHONE"
                elif input_type in ["number"]:
                    field_type = "NUMBER"
                elif input_type in ["date"]:
                    field_type = "DATE"
                elif input_type in ["file"]:
                    field_type = "FILE_UPLOAD"
                elif input_type in ["checkbox"]:
                    field_type = "CHECKBOX"
                elif input_type in ["radio"]:
                    field_type = "RADIO"
                elif elem_type == "select":
                    field_type = "SELECT"
                elif elem_type == "textarea":
                    field_type = "TEXTAREA"

                options = []
                if elem_type == "select":
                    for option in elem.find_all("option"):
                        val = option.get("value") or option.get_text(strip=True)
                        if val:
                            options.append(val)

                fields.append({
                    "field_name": field_name,
                    "label": label_text,
                    "field_type": field_type,
                    "required": required,
                    "options": options
                })

            if not fields:
                return self._get_default_form_fields()

            return fields

        except Exception as e:
            logger.warning(f"HTML form extraction error: {e}. Falling back to default form template.")
            return self._get_default_form_fields()

    def _get_default_form_fields(self) -> List[Dict[str, Any]]:
        """Standard fallback fields for candidate applications."""
        return [
            {
                "field_name": "first_name",
                "label": "First Name",
                "field_type": "TEXT",
                "required": True,
                "options": []
            },
            {
                "field_name": "last_name",
                "label": "Last Name",
                "field_type": "TEXT",
                "required": True,
                "options": []
            },
            {
                "field_name": "email",
                "label": "Email Address",
                "field_type": "EMAIL",
                "required": True,
                "options": []
            },
            {
                "field_name": "phone",
                "label": "Phone Number",
                "field_type": "PHONE",
                "required": False,
                "options": []
            },
            {
                "field_name": "location",
                "label": "Current Location / City",
                "field_type": "TEXT",
                "required": False,
                "options": []
            },
            {
                "field_name": "linkedin_url",
                "label": "LinkedIn Profile URL",
                "field_type": "TEXT",
                "required": False,
                "options": []
            },
            {
                "field_name": "github_url",
                "label": "GitHub Profile / Portfolio URL",
                "field_type": "TEXT",
                "required": False,
                "options": []
            },
            {
                "field_name": "work_authorization",
                "label": "Are you legally authorized to work in this country?",
                "field_type": "SELECT",
                "required": True,
                "options": ["Yes", "No", "Require Sponsorship"]
            },
            {
                "field_name": "resume",
                "label": "Attach Resume / CV",
                "field_type": "FILE_UPLOAD",
                "required": True,
                "options": []
            },
            {
                "field_name": "why_work_here",
                "label": "Why do you want to work at this company?",
                "field_type": "TEXTAREA",
                "required": False,
                "options": []
            }
        ]
