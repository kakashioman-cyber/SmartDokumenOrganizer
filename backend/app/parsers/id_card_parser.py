import re
from .base_parser import BaseDocumentParser
from .ktp_parser import KTPParser
from .passport_parser import PassportParser

class IDCardParser(BaseDocumentParser):
    """Modular Router for Identity Documents (Delegates to KTPParser & PassportParser)."""

    def parse(self, prompt: str, forced_type: str = None) -> dict:
        lines = [l.strip() for l in prompt.split('\n') if l.strip()]
        
        ktp_p = KTPParser()
        pass_p = PassportParser()

        if forced_type == "ktp":
            return ktp_p.parse(prompt, lines)
        elif forced_type == "passport":
            return pass_p.parse(prompt, lines)

        # Smart automatic detection
        has_ktp_indicators = any(kw in prompt.upper() for kw in ["NIK", "PROVINSI", "KOTA", "AGAMA", "RT/RW", "KEL/DESA", "KECAMATAN", "BERLAKU HINGGA"])
        has_passport_indicators = any(kw in prompt.upper() for kw in ["P<", "PASSPORT NO", "PASPOR NO", "COUNTRY CODE", "ISSUING OFFICE", "PASSPORT"])

        if has_passport_indicators and not has_ktp_indicators:
            return pass_p.parse(prompt, lines)
        else:
            return ktp_p.parse(prompt, lines)

    def _parse_passport(self, prompt: str, lines: list) -> dict:
        return PassportParser().parse(prompt, lines)

    def _parse_ktp(self, prompt: str, lines: list) -> dict:
        return KTPParser().parse(prompt, lines)
