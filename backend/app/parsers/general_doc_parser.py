import re
from .base_parser import BaseDocumentParser

class GeneralDocumentParser(BaseDocumentParser):
    """Modular Parser for Business, Tax (NPWP), License (NIB), and General Documents."""
    
    def parse(self, prompt: str) -> dict:
        gen_data = {
            "document_title": "N/A",
            "tax_id_npwp": "N/A",
            "business_license_nib": "N/A",
            "certificate_number": "N/A",
            "issue_date": "N/A",
            "summary": "N/A"
        }

        # 1. Document Title
        lines = [l.strip() for l in prompt.split('\n') if l.strip()]
        if lines:
            gen_data["document_title"] = lines[0]

        # 2. NPWP / Tax ID
        npwp_match = re.search(r'\b\d{2}\.?\d{3}\.?\d{3}\.?\d{1}-\d{3}\.?\d{3}\b|(?:NPWP|Tax ID)\s*[:.-]?[ \t]*([0-9.-]+)', prompt, flags=re.IGNORECASE)
        if npwp_match:
            gen_data["tax_id_npwp"] = npwp_match.group(0).strip()

        # 3. NIB / Business License
        nib_match = re.search(r'(?:NIB|No\.?\s*NIB|Nomor Induk Berusaha|SIUP)\s*[:.-]?[ \t]*([A-Z0-9.-]+)', prompt, flags=re.IGNORECASE)
        if nib_match:
            gen_data["business_license_nib"] = nib_match.group(1).strip()

        # 4. Certificate Number
        cert_match = re.search(r'(?:No\.?\s*Sertifikat|Certificate No|No\.?\s*Izin)\s*[:.-]?[ \t]*([A-Z0-9.-]+)', prompt, flags=re.IGNORECASE)
        if cert_match:
            gen_data["certificate_number"] = cert_match.group(1).strip()

        # 5. Issue Date
        date_match = re.search(r'(?:Date|Tanggal|Tgl\.?\s*Terbit)\s*[:.-]?[ \t]*(\d{1,2}[-./]\d{1,2}[-./]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})', prompt, flags=re.IGNORECASE)
        if date_match:
            gen_data["issue_date"] = date_match.group(1).strip()

        # 6. Summary
        gen_data["summary"] = prompt[:300].replace('\n', ' ').strip() + ("..." if len(prompt) > 300 else "")

        # Sanitize return fields
        for k, v in gen_data.items():
            if isinstance(v, str):
                gen_data[k] = self.sanitize_str(v)

        return gen_data
