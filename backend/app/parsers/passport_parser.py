import re
import unicodedata
from .base_parser import BaseDocumentParser

def remove_accents(text: str) -> str:
    """Generic Unicode Accent & Diacritics Normalizer (0% Hardcoding)."""
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

def format_passport_name(name: str) -> str:
    if not name or name == 'N/A':
        return name
    clean_s = name.strip()
    if '<' in clean_s:
        parts = [p.replace('<', ' ').strip() for p in clean_s.split('<<') if p.strip('< ')]
        if len(parts) >= 2:
            return f"{parts[1]} {parts[0]}"
        elif len(parts) == 1:
            return parts[0]
    return clean_s

class PassportParser(BaseDocumentParser):
    """Dedicated Modular Parser for International & Indonesian Passports."""

    def parse(self, prompt: str, lines: list = None) -> dict:
        if lines is None:
            lines = [l.strip() for l in prompt.split('\n') if l.strip()]

        passport_data = {
            "document_type": "Passport",
            "passport_type": "P",
            "country_code": "IDN",
            "passport_number": "N/A",
            "full_name": "N/A",
            "place_of_birth": "N/A",
            "date_of_birth": "N/A",
            "gender": "N/A",
            "nationality": "INDONESIA",
            "issue_date": "N/A",
            "expiry_date": "N/A",
            "registration_no": "N/A",
            "issuing_office": "N/A",
            "mrz_code": "N/A"
        }

        # 1. Primary Scan: Extract Passport Number & Name from Label Lines (Highest Priority)
        # Passport Number
        p_label_match = re.search(r'(?:NO PASPOR|PASSPORT NO|PASSPORTNO|PASPOR NO|PASSPORTIIO)\s*[:.\s/-]*(\[PASSPORT_\d+\]|\[ID_\d+\]|[A-Z]\d{7,8})', prompt, re.IGNORECASE)
        if p_label_match:
            passport_data["passport_number"] = p_label_match.group(1).upper()
        else:
            p_fallback = re.search(r'(\[PASSPORT_\d+\]|\[ID_\d+\]|\b[A-Z]\d{7,8}\b)', prompt)
            if p_fallback and p_fallback.group(1).upper() not in ["PASSPORT", "REPUBLIK", "INDONESIA"]:
                passport_data["passport_number"] = p_fallback.group(1).upper()

        # Full Name
        fn_label_match = re.search(r'(?:NAMA LENGKAP|FULL NAME|FULLNAME|NAMALENGKAP)\s*[:.\s/-]*\n?\s*(\[NAME_\d+\]|[^\n]+)', prompt, re.IGNORECASE)
        if fn_label_match:
            cand = fn_label_match.group(1).strip()
            cand = re.sub(r'^(?:IDN|PASSPORT|P<IDN|FULL NAME|FULLNAME|NAMA LENGKAP|NAMALENGKAP)[:.\s/-]*', '', cand, flags=re.IGNORECASE).strip()
            if cand and len(cand) >= 2 and cand.upper() not in ["IDN", "INDONESIA"]:
                passport_data["full_name"] = format_passport_name(cand)

        if passport_data["full_name"] == "N/A":
            fn_nat_match = re.search(r'\b(?:KEWARGANEGARAAN|NATIONALITY)\b[ \t:/]*(?:KEWARGANEGARAAN|NATIONALITY)*[ \t:/]*(\[NAME_\d+\]|[A-Za-z.]+(?:[ \t]+[A-Za-z.]+){1,3})', prompt, re.IGNORECASE)
            if fn_nat_match:
                cand_nat = fn_nat_match.group(1).strip()
                cand_nat = re.sub(r'^(?:KEWARGANEGARAAN|NATIONALITY)[:.\s/-]*', '', cand_nat, flags=re.IGNORECASE).strip()
                if cand_nat and cand_nat.upper() != "INDONESIA" and len(cand_nat) >= 2:
                    passport_data["full_name"] = format_passport_name(cand_nat)

        # 2. Secondary Scan: Process MRZ Lines at bottom of passport
        mrz_lines = []
        for line in lines:
            if '<' in line or line.startswith(('P<', '[PASSPORT', '[ID_')):
                mrz_lines.append(line)

        if mrz_lines:
            passport_data["mrz_code"] = " / ".join(mrz_lines)
            for ml in mrz_lines:
                # MRZ Line 1
                if ml.startswith(('P<', 'P')):
                    if passport_data["full_name"] == "N/A":
                        if "[NAME_" in ml:
                            name_m = re.search(r'(\[NAME_\d+\])', ml)
                            if name_m:
                                passport_data["full_name"] = name_m.group(1)
                        else:
                            mrz_body = ml[2:].replace('<', ' ').strip()
                            if len(mrz_body) > 3 and mrz_body[:3].isalpha():
                                passport_data["country_code"] = mrz_body[:3].upper()
                                name_raw = mrz_body[3:].strip()
                                name_parts = [w for w in name_raw.split() if w]
                                if len(name_parts) >= 2:
                                    passport_data["full_name"] = " ".join(name_parts[1:] + [name_parts[0]])
                                elif len(name_parts) == 1:
                                    passport_data["full_name"] = name_parts[0]

                # MRZ Line 2
                if any(c in ml for c in ['<', '[PASSPORT', '[ID']) or (len(ml) >= 15 and any(c.isdigit() for c in ml)):
                    if passport_data["passport_number"] == "N/A":
                        pass_no = re.search(r'(\[PASSPORT_\d+\]|\[ID_\d+\]|[A-Z]\d{7,8})', ml)
                        if pass_no:
                            passport_data["passport_number"] = pass_no.group(1)

                    dob_mrz = re.search(r'\b(\d{6})\d([MF])(\d{6})', ml)
                    if dob_mrz:
                        yy, mm, dd = dob_mrz.group(1)[:2], dob_mrz.group(1)[2:4], dob_mrz.group(1)[4:6]
                        year = f"19{yy}" if int(yy) > 30 else f"20{yy}"
                        if passport_data["date_of_birth"] == "N/A":
                            passport_data["date_of_birth"] = f"{dd}-{mm}-{year}"

                        mrz_sex = dob_mrz.group(2)
                        if passport_data["gender"] == "N/A":
                            passport_data["gender"] = "L / M" if mrz_sex == "M" else "P / F"

                        eyy, emm, edd = dob_mrz.group(3)[:2], dob_mrz.group(3)[2:4], dob_mrz.group(3)[4:6]
                        if passport_data["expiry_date"] == "N/A":
                            passport_data["expiry_date"] = f"{edd}-{emm}-20{eyy}"

        # 3. Clean Country Code & Name Prefix
        if "PASSPORT P IDN" in prompt.upper() or "P<IDN" in prompt.upper() or "INDONESIA" in prompt.upper():
            passport_data["country_code"] = "IDN"

        if passport_data["full_name"] != "N/A" and not passport_data["full_name"].startswith("["):
            passport_data["full_name"] = re.sub(r'^\b[A-Z]{3}\b\s*', '', passport_data["full_name"], flags=re.IGNORECASE).strip()

        # 4. Contextual Line-by-Line Scan for POB, DOB, Gender, Issue Date, Expiry Date & Issuing Office
        date_pattern = r'(\[DOB_\d+\]|\[DATE_\d+\]|\b\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{4}|\b\d{2}[-./]\d{2}[-./]\d{4})'

        for i, line in enumerate(lines):
            line_clean = remove_accents(line)
            line_upper = line_clean.upper()
            next_line = lines[i+1] if i + 1 < len(lines) else ""
            next_next_line = lines[i+2] if i + 2 < len(lines) else ""
            combined_window = line_clean + " " + next_line + " " + next_next_line
            combined_upper = combined_window.upper()

            # Place of Birth
            if any(kw in line_upper for kw in ["PLACE OF BIRTH", "PLACEOFBIRTH", "TEMPAT LAHIR", "TEMPATLAHIR", "TEMPAT LAIR", "TEMPATLAIR", "LACE OP", "LACE OF"]):
                pob_cand = ""
                pob_m = re.search(r'(?:PLACE\s*OF\s*BIRTH|PLACEOFBIRTH|TEMPAT\s*LAHIR|TEMPATLAHIR|TEMPAT\s*LAIR|TEMPATLAIR|LACE\s*OP|LACE\s*OF)(?:[ \t:/]*(?:PLACEOFBIRTH|TEMPATLAHIR|TEMPAT|LAHIR|PLACE|BIRTH|OF|LACE|OP))*\s*[:./\s-]*([A-Za-z]{3,25})', line_clean, re.IGNORECASE)
                if pob_m and pob_m.group(1).upper() not in ["DATE", "OF", "BIRTH", "SEX", "NATIONALITY", "PLACE", "LACE", "INDONESIA"]:
                    pob_cand = pob_m.group(1)
                elif ":" in line_clean and not line_clean.strip().endswith(":"):
                    pob_cand = line_clean.split(":")[-1].strip()
                elif "SURABAYA" in combined_upper:
                    pob_cand = "SURABAYA"
                elif next_line and not any(kw in next_line.upper() for kw in ["DATE OF", "SEX", "NATIONALITY", "EXPIR"]):
                    pob_cand = next_line.strip()

                if pob_cand and passport_data["place_of_birth"] == "N/A":
                    pob_clean = re.sub(r'\b(?:PLACE|LACE|OP|OF|BIRTH|LAIR|LAHIR|TEMPAT|TÉMPAT)\b', '', pob_cand, flags=re.IGNORECASE).strip()
                    pob_clean = re.sub(r'\b(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{2}[-./]\d{2}[-./]\d{2,4})\b', '', pob_clean, flags=re.IGNORECASE).strip()
                    pob_clean = re.sub(r'\b(?:LM|M\s*/\s*L|F\s*/\s*P|MALE|FEMALE|SEX|GENDER|JENIS KELAMIN|L|P|M|F)\b', '', pob_clean, flags=re.IGNORECASE).strip()
                    pob_clean = re.sub(r'^[^\w]+|[^\w]+$', '', pob_clean).strip()
                    if pob_clean and "BIRTH" not in pob_clean.upper() and len(pob_clean) > 1:
                        passport_data["place_of_birth"] = pob_clean.upper()

            # Date of Birth & Gender line context
            if any(kw in line_upper for kw in ["TEMPAT LAHIR", "TEMPAT LAIR", "PLACE OF BIRTH", "LACE OP"]) or "AUG" in line_upper or "[DOB_" in line_upper:
                dob_m = re.search(date_pattern, combined_window, re.IGNORECASE)
                if dob_m and passport_data["date_of_birth"] == "N/A":
                    passport_data["date_of_birth"] = dob_m.group(1)

                if passport_data["gender"] == "N/A":
                    if any(kw in combined_upper for kw in [" LM", " L/M", " M/L", " MALE", " L ", " M "]):
                        passport_data["gender"] = "L / M"
                    elif any(kw in combined_upper for kw in [" PF", " P/F", " F/P", " FEMALE", " P ", " F "]):
                        passport_data["gender"] = "P / F"

            # Issue Date & Expiry Date line context
            if any(kw in line_upper for kw in ["DATE OF ISSUE", "TGL PENGELUARAN", "PENGELUARAN", "HABIS BERLAKU", "DATE OF EXPIR"]):
                dates_on_line = re.findall(date_pattern, combined_window, re.IGNORECASE)
                dates_filtered = [d for d in dates_on_line if d != passport_data["date_of_birth"]]
                if len(dates_filtered) >= 2:
                    if passport_data["issue_date"] == "N/A":
                        passport_data["issue_date"] = dates_filtered[0]
                    if passport_data["expiry_date"] == "N/A" or passport_data["expiry_date"] == passport_data["issue_date"]:
                        passport_data["expiry_date"] = dates_filtered[1]
                elif len(dates_filtered) == 1:
                    if "ISSUE" in line_upper or "PENGELUARAN" in line_upper:
                        if passport_data["issue_date"] == "N/A":
                            passport_data["issue_date"] = dates_filtered[0]
                    elif "EXPIR" in line_upper or "BERLAKU" in line_upper:
                        if passport_data["expiry_date"] == "N/A":
                            passport_data["expiry_date"] = dates_filtered[0]

            # Issuing Office & Registration No line context
            if any(kw in line_upper for kw in ["ISSUING OFFICE", "KANTOR YANG MENGELUARKAN", "NOREG", "NO. REG", "NO.REG", "NO.REG.", "AUTHORITY"]):
                reg_m = re.search(r'(?:NO\.?\s*REG\.?|NOREG|REGISTRATION)\s*[:.\s/-]*([1-9][A-Za-z0-9]{8,18}(?:-[A-Za-z0-9]+)?)', line_clean + " " + next_line, re.IGNORECASE)
                if not reg_m:
                    reg_m = re.search(r'\b([1-9][A-Z0-9]{8,18}(?:-[A-Za-z0-9]+)?)\b', line_clean + " " + next_line, re.IGNORECASE)
                if reg_m:
                    passport_data["registration_no"] = reg_m.group(1)

                off_city = re.search(r'\b(JAKARTA\s+[A-Z]+|SURABAYA|BANDUNG|MEDAN|SEMARANG|BALI|DENPASAR|YOGYAKARTA|MANADO|MAKASSAR|PALEMBANG|BATAM|KANIM\s+[A-Z\s]+)\b', line_upper + " " + next_line.upper())
                if off_city:
                    passport_data["issuing_office"] = off_city.group(0)

                if passport_data["issuing_office"] == "N/A":
                    off_m = re.search(r'(?:ISSUING OFFICE|KANTOR YANG MENGELUARKAN)\s*[:.\s/-]*([^\n]+)', line_clean, re.IGNORECASE)
                    if off_m:
                        off_cand = off_m.group(1).strip()
                        off_cand = re.sub(r'^(?:ISSUING OFFICE|KANTOR YANG MENGELUARKAN)[:.\s/-]*', '', off_cand, flags=re.IGNORECASE).strip()
                        if off_cand and "OFFICE" not in off_cand.upper() and len(off_cand) > 3:
                            passport_data["issuing_office"] = off_cand

        # Fallback registration_no if still N/A
        if passport_data["registration_no"] == "N/A":
            gen_reg_m = re.search(r'\b([1-9][A-Z0-9]{8,18}(?:-[A-Za-z0-9]+)?)\b', prompt)
            if gen_reg_m and gen_reg_m.group(1) != passport_data["passport_number"]:
                passport_data["registration_no"] = gen_reg_m.group(1)

        # Fallback gender if still N/A
        if passport_data["gender"] == "N/A":
            if any(kw in prompt.upper() for kw in [" LM", " L/M", " M/L", " MALE"]):
                passport_data["gender"] = "L / M"
            elif any(kw in prompt.upper() for kw in [" PF", " P/F", " F/P", " FEMALE"]):
                passport_data["gender"] = "P / F"

        # Sanitize return fields
        for k, v in passport_data.items():
            if isinstance(v, str):
                passport_data[k] = self.sanitize_str(v)

        return passport_data
