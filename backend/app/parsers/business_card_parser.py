import re
from .base_parser import BaseDocumentParser

class BusinessCardParser(BaseDocumentParser):
    """Modular Parser for Business Cards (Kartu Nama)."""
    
    def parse(self, prompt: str) -> dict:
        card_data = {
            "contact_name": "N/A",
            "job_title": "N/A",
            "company_name": "N/A",
            "phone_number": "N/A",
            "email_address": "N/A",
            "office_address": "N/A",
            "website_url": "N/A"
        }

        # Email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b|\[EMAIL_\d+\]', prompt)
        if email_match:
            card_data["email_address"] = email_match.group(0).strip()

        # Phone
        phone_match = re.search(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b|\[PHONE_\d+\]', prompt)
        if phone_match:
            card_data["phone_number"] = phone_match.group(0).strip()

        # Contact Name
        name_match = re.search(r'(?:Name|Nama|Contact)\s*[:.-]?[ \t]*([A-Za-z\s]+|\[NAME_\d+\])', prompt, flags=re.IGNORECASE)
        if name_match:
            card_data["contact_name"] = name_match.group(1).strip()

        # Company Name
        comp_match = re.search(r'(?:PT\.?|CV\.?|Inc\.?|Corp\.?|Company|Perusahaan)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        if comp_match:
            card_data["company_name"] = comp_match.group(0).strip()

        # Website
        web_match = re.search(r'\b(?:https?://|www\.)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', prompt, flags=re.IGNORECASE)
        if web_match:
            card_data["website_url"] = web_match.group(0).strip()

        # Sanitize return fields
        for k, v in card_data.items():
            if isinstance(v, str):
                card_data[k] = self.sanitize_str(v)

        return card_data
