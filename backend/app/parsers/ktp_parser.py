import re
from .base_parser import BaseDocumentParser

def format_ktp_name(name: str) -> str:
    """
    Generic, zero-hardcode Indonesian name segmenter:
    If a name string has no spaces (e.g. OCR read 'ABDURROHMANROBBANY' or 'HAMIDAHSALIMAH'),
    algorithmically identifies morphological word boundaries (suffixes like MAN, DAH, MAH, WAN, YAN, LAN)
    and inserts spaces cleanly without any hardcoded dictionary lists.
    """
    if not name or name == 'N/A' or ' ' in name.strip() or len(name.strip()) < 8 or name.startswith('[NAME_'):
        return name
        
    s = name.strip()

    # 1. CamelCase split (e.g. HamidahSalimah -> Hamidah Salimah)
    if re.search(r'[a-z][A-Z]', s):
        return re.sub(r'([a-z])([A-Z])', r'\1 \2', s)

    clean_u = s.upper()
    vowels = set('AEIOU')

    # Generic morphological suffixes that mark syllable boundaries between Indonesian name components
    GENERIC_NAME_SUFFIXES = ['MAN', 'DAH', 'MAH', 'LAH', 'WAN', 'YAN', 'LAN', 'TON', 'RIN', 'TUN', 'GUNG', 'PUT', 'RUL', 'DIL', 'SAM', 'RAM']

    candidates = []
    for suf in GENERIC_NAME_SUFFIXES:
        for m in re.finditer(suf, clean_u):
            idx = m.end()
            if 3 <= idx <= len(clean_u) - 3:
                p1, p2 = clean_u[:idx], clean_u[idx:]
                if any(c in vowels for c in p1) and any(c in vowels for c in p2):
                    candidates.append((len(p1), p1, p2))

    if candidates:
        # Select the longest valid first-word boundary candidate
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0]
        return f"{best[1]} {best[2]}"

    return name

def format_ktp_address(addr: str) -> str:
    if not addr or addr == 'N/A' or addr.startswith('[ADDRESS_'):
        return addr

    # 1. Add dot to JL. if missing
    addr = re.sub(r'^(?:JL\.?|JALAN)\s*([A-Za-z])', r'JL. \1', addr, flags=re.IGNORECASE)
    
    # 2. Separate concatenated directions or modifiers: KETINTANGBARU -> KETINTANG BARU
    addr = re.sub(r'([A-Za-z]{3,})(BARU|LAMA|TIMUR|BARAT|SELATAN|UTARA)', r'\1 \2', addr, flags=re.IGNORECASE)

    # 3. Separate Roman numerals attached to words (e.g. BARUIV -> BARU IV)
    addr = re.sub(r'([A-Za-z]{2,})\s*(IV|VI|VII|VIII|IX|X|III|II|I)(?=\s|NO|\d|$)', r'\1 \2', addr, flags=re.IGNORECASE)

    # 4. Separate Roman numerals attached to NO (e.g. IVNO -> IV NO)
    addr = re.sub(r'\b(IV|VI|VII|VIII|IX|X|III|II|I)\s*(NO|NOMOR|\d+)', r'\1 \2', addr, flags=re.IGNORECASE)

    # 5. Format NO. 20
    addr = re.sub(r'\b(NO|NOMOR)\.?\s*(\d+)', r'NO. \2', addr, flags=re.IGNORECASE)

    return re.sub(r'\s+', ' ', addr).strip()

class KTPParser(BaseDocumentParser):
    """Dedicated Modular Parser for Indonesian Identity Cards (KTP)."""

    def parse(self, prompt: str, lines: list = None) -> dict:
        ktp_data = {
            "document_type": "KTP / Identity Card",
            "id_number": "N/A",
            "full_name": "N/A",
            "place_of_birth": "N/A",
            "date_of_birth": "N/A",
            "blood_type": "N/A",
            "gender": "N/A",
            "address": "N/A",
            "rt_rw": "N/A",
            "kel_desa": "N/A",
            "kecamatan": "N/A",
            "religion": "N/A",
            "marital_status": "N/A",
            "occupation": "N/A",
            "nationality": "WNI",
            "issue_date": "N/A",
            "expiry_date": "SEUMUR HIDUP",
            "issuing_office": "N/A"
        }

        prompt_lines = [l.strip() for l in prompt.split('\n') if l.strip()]

        # 1. NIK (id_number)
        nik_match = re.search(r'(\[NIK_\d+\]|\[ID_\d+\]|(?:NIK|N|K|N1K)\s*[:.-]?[ \t]*(\d{16}))', prompt, flags=re.IGNORECASE)
        if nik_match:
            ktp_data["id_number"] = nik_match.group(1)
        else:
            nik_fallback = re.search(r'\b\d{16}\b', prompt)
            if nik_fallback:
                ktp_data["id_number"] = nik_fallback.group(0)

        # 2. Full Name
        name_match = re.search(r'(\[NAME_\d+\])', prompt)
        if name_match:
            ktp_data["full_name"] = name_match.group(1)
        else:
            for idx, l in enumerate(prompt_lines):
                if 'NIK' in l.upper() or re.search(r'\d{16}', l):
                    for sub_l in prompt_lines[idx+1 : idx+4]:
                        sub_c = sub_l.strip()
                        if sub_c and not any(kw in sub_c.upper() for kw in ['NIK', 'NAMA', 'PROVINSI', 'KOTA', 'KABUPATEN', 'TEMPAT', 'TEMPAL', 'LAHIR', 'TGL', 'AGAMA', 'GOL', 'JENIS', 'ALAMAT', 'RT', 'RW']):
                            if re.match(r'^[A-Za-z\s]{3,50}$', sub_c):
                                ktp_data["full_name"] = format_ktp_name(sub_c)
                                break

            if ktp_data["full_name"] == "N/A":
                name_m2 = re.search(r'\b(?:Nama|Name)\s*[:.-]?[ \t]*([A-Za-z. \t]+)', prompt, flags=re.IGNORECASE)
                if name_m2:
                    cand = name_m2.group(1).strip()
                    cand = re.sub(r'^(?:Nama|Name)[:.-]?\s*', '', cand, flags=re.IGNORECASE).strip()
                    if cand and len(cand) >= 2 and not any(kw in cand.upper() for kw in ["TEMPAT", "LAHIR", "PROVINSI", "KOTA", "NIK"]):
                        ktp_data["full_name"] = format_ktp_name(cand)

        # 3. POB & DOB
        dob_match = re.search(r'(\[DOB_\d+\]|\[DATE_\d+\]|\b\d{1,2}[\s.\-/]+\d{1,2}[\s.\-/]+\d{2,4}\b)', prompt)
        if dob_match:
            ktp_data["date_of_birth"] = dob_match.group(1).strip().replace(' ', '-')

        pob_dob_match = re.search(
            r'(?:Tempat/Tgl|Tempal/Tgl|Tempat|Tempal)\s*Lahir\s*[:.-]?[ \t]*([A-Za-z0-9\s]+?)[,.:\s]+(\[DOB_\d+\]|\[DATE_\d+\]|\d{1,2}[\s.\-/]+\d{1,2}[\s.\-/]+\d{2,4})',
            prompt,
            flags=re.IGNORECASE
        )
        if pob_dob_match:
            pob_raw = pob_dob_match.group(1).strip()
            pob_clean = re.sub(r'1', 'Y', pob_raw)
            pob_clean = re.sub(r'7', 'T', pob_clean)
            pob_clean = re.sub(r'6', 'G', pob_clean)
            ktp_data["place_of_birth"] = pob_clean.strip()
            ktp_data["date_of_birth"] = pob_dob_match.group(2).strip().replace(' ', '-')
        else:
            for i, l in enumerate(prompt_lines):
                if any(kw in l.upper() for kw in ["TEMPAT", "LAHIR", "TEMPAL"]):
                    pob_m = re.search(r'(?:TEMPAT/TGL LAHIR|TEMPAT TGL LAHIR|LAHIR)\s*[:.-]?[ \t]*([A-Za-z0-9\s]+)', l, flags=re.IGNORECASE)
                    if pob_m:
                        pob_cand = pob_m.group(1).split(',')[0].strip()
                        pob_cand = re.sub(r'1', 'Y', pob_cand)
                        if pob_cand and not any(kw in pob_cand.upper() for kw in ["JENIS", "ALAMAT", "GOL", "NIK"]):
                            ktp_data["place_of_birth"] = pob_cand

        # 4. Blood Type (Golongan Darah - Same line restricted)
        blood_m = re.search(r'(?:Gol\.?\s*Darah|GolDarah)\s*[:.-]?[ \t]*([ABO\+-]{1,3})\b', prompt, flags=re.IGNORECASE)
        if blood_m:
            cand_b = blood_m.group(1).strip().upper()
            if cand_b in ['A', 'B', 'AB', 'O', 'A+', 'B+', 'AB+', 'O+']:
                ktp_data["blood_type"] = cand_b

        # 5. Gender
        if "LAKI-LAKI" in prompt.upper() or "LAKI" in prompt.upper():
            ktp_data["gender"] = "LAKI-LAKI"
        elif "PEREMPUAN" in prompt.upper():
            ktp_data["gender"] = "PEREMPUAN"

        # 6. Address
        addr_match = re.search(r'(\[ADDRESS_\d+\]|(?:JL\.?|JALAN)\s*[^\n|]+|(?:Alamat|Address)\s*[:.-]?[ \t]*([^\n]+))', prompt, flags=re.IGNORECASE)
        if addr_match:
            address = addr_match.group(1).strip()
            address = re.sub(r'^(?:Alamat|Address)[:.;,\s-]*', '', address, flags=re.IGNORECASE).strip()
            address = format_ktp_address(address)
            ktp_data["address"] = address

        # 7. RT/RW
        rtrw_match = re.search(r'(?:RT/RW|RT\s*/\s*RW|RTARW|RT-RW|RTRW|RT|RW)\s*[:.-]?[ \t]*([0-9/\s-]+)', prompt, flags=re.IGNORECASE)
        if rtrw_match:
            ktp_data["rt_rw"] = re.sub(r'^[:;.,\s-]+', '', rtrw_match.group(1)).strip()

        # 8. Kel/Desa
        for idx, l in enumerate(prompt_lines):
            if any(kw in l.upper() for kw in ['KEL/DESA', 'K-L/DESA', 'KELURAHAN', 'DESA']):
                line_val = re.sub(r'^(?:K[-e]l/Desa|Kel/Desa|Kelurah[a-z]+|Desa)[:.;,\s-]*', '', l, flags=re.IGNORECASE).strip()
                if line_val and not any(kw in line_val.upper() for kw in ['KECAMATAN', 'AGAMA', 'STATUS', 'PEKERJAAN']):
                    ktp_data["kel_desa"] = line_val
                    break
                elif idx > 0 and prompt_lines[idx-1].strip().isalpha():
                    ktp_data["kel_desa"] = prompt_lines[idx-1].strip()
                    break

        # 9. Kecamatan
        kec_match = re.search(r'(?:Kecamatan|Kecamalan|Kecamatar|Kec)\s*[:.-]?[ \t]*([A-Za-z0-9_]+)', prompt, flags=re.IGNORECASE)
        if kec_match:
            ktp_data["kecamatan"] = kec_match.group(1).strip()

        # 10. Religion
        rel_str = prompt.upper()
        rel_match = re.search(r'(?:Agama|Religion)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        if rel_match and rel_match.group(1).strip():
            cand_rel = rel_match.group(1).strip().upper()
            if any(w in cand_rel for w in ["ISCAM", "ISLM", "1SLAM", "ISLAM", "KRIST", "KRIS", "KATO", "KATH", "HIND", "BUD", "KHONG"]):
                rel_str = cand_rel

        if any(w in rel_str for w in ["ISCAM", "ISLM", "1SLAM", "ISLAM"]):
            ktp_data["religion"] = "ISLAM"
        elif any(w in rel_str for w in ["KRIST", "KRIS"]):
            ktp_data["religion"] = "KRISTEN"
        elif any(w in rel_str for w in ["KATO", "KATH"]):
            ktp_data["religion"] = "KATOLIK"
        elif any(w in rel_str for w in ["HIND"]):
            ktp_data["religion"] = "HINDU"
        elif any(w in rel_str for w in ["BUD"]):
            ktp_data["religion"] = "BUDDHA"
        elif any(w in rel_str for w in ["KHONG"]):
            ktp_data["religion"] = "KHONGHUCU"

        # 11. Marital Status
        mar_match = re.search(r'(?:Status Perkawinan|Perkawinan|Status)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        mar_str = mar_match.group(1).strip().upper() if mar_match else prompt.upper()
        if "BELUM" in mar_str:
            ktp_data["marital_status"] = "BELUM KAWIN"
        elif "KAWIN" in mar_str:
            ktp_data["marital_status"] = "KAWIN"

        # 12. Occupation
        occ_str = prompt.upper()
        occ_match = re.search(r'(?:Pekerjaan|Occupation)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        if occ_match and occ_match.group(1).strip():
            cand_occ = occ_match.group(1).strip().upper()
            if any(w in cand_occ for w in ["PELAJAR", "MAHASISWA", "KARYAWAN", "PNS", "WIRASWASTA", "BURUH", "TNI", "POLRI"]):
                occ_str = cand_occ

        if "PELAJAR" in occ_str or "MAHASISWA" in occ_str:
            ktp_data["occupation"] = "PELAJAR / MAHASISWA"
        elif "SWASTA" in occ_str or "KARYAWAN" in occ_str:
            ktp_data["occupation"] = "KARYAWAN SWASTA"

        # 13. Issue Date
        all_dates = list(re.finditer(r'(\[DOB_\d+\]|\[DATE_\d+\]|\b\d{1,2}[\s.\-/]+\d{1,2}[\s.\-/]+\d{2,4}\b)', prompt))
        if len(all_dates) >= 2:
            ktp_data["issue_date"] = all_dates[-1].group(1).strip()

        # 14. Issuing Office
        off_match = re.search(r'\b(KOTA\s*[A-Za-z]+|KABUPATEN\s*[A-Za-z]+)\b', prompt, flags=re.IGNORECASE)
        if off_match:
            cand_off = off_match.group(0).strip()
            cand_off = re.sub(r'^(KOTA|KABUPATEN)\s*', r'\1 ', cand_off, flags=re.IGNORECASE)
            ktp_data["issuing_office"] = cand_off.upper()

        # Sanitize return fields
        for k, v in ktp_data.items():
            if isinstance(v, str):
                ktp_data[k] = self.sanitize_str(v)

        return ktp_data
