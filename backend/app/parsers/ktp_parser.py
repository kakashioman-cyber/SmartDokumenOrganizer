import re
from .base_parser import BaseDocumentParser

class KTPParser(BaseDocumentParser):
    """Dedicated Modular Parser for Indonesian Identity Cards (KTP)."""

    def parse(self, prompt: str, lines: list) -> dict:
        ktp_data = {
            "document_type": "KTP / Identity Card",
            "id_number": "N/A",
            "full_name": "N/A",
            "place_of_birth": "N/A",
            "date_of_birth": "N/A",
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
            name_m2 = re.search(r'\b(?:Nama|Name)\s*[:.-]?[ \t]*([A-Za-z \t]+)', prompt, flags=re.IGNORECASE)
            if name_m2:
                cand = name_m2.group(1).strip()
                cand = re.sub(r'^(?:Nama|Name)[:.-]?\s*', '', cand, flags=re.IGNORECASE).strip()
                if cand and len(cand) >= 2 and not any(kw in cand.upper() for kw in ["TEMPAT", "LAHIR", "PROVINSI", "KOTA", "NIK"]):
                    ktp_data["full_name"] = cand

        # 3. DOB & POB
        dob_match = re.search(r'(\[DOB_\d+\]|\[DATE_\d+\]|\b\d{1,2}[\s.\-/]+\d{1,2}[\s.\-/]+\d{2,4}\b)', prompt)
        if dob_match:
            ktp_data["date_of_birth"] = dob_match.group(1).strip().replace(' ', '-')

        pob_dob_match = re.search(
            r'(?:Tempat/Tgl Lahir|Tempat Tgl Lahir|Tempat/Tanggal Lahir|TempalTgl Lahir|Tgl Lahir)\s*[:.-]?[ \t]*([A-Za-z\s]+?)[,.:\s]+(\[DOB_\d+\]|\[DATE_\d+\]|\d{1,2}[\s.\-/]+\d{1,2}[\s.\-/]+\d{2,4})',
            prompt,
            flags=re.IGNORECASE
        )
        if pob_dob_match:
            ktp_data["place_of_birth"] = pob_dob_match.group(1).strip()
            ktp_data["date_of_birth"] = pob_dob_match.group(2).strip().replace(' ', '-')
        else:
            for i, l in enumerate(lines):
                if any(kw in l.upper() for kw in ["TEMPAT", "LAHIR", "TEMPAL"]):
                    pob_m = re.search(r'(?:TEMPAT/TGL LAHIR|TEMPAT TGL LAHIR|LAHIR)\s*[:.-]?[ \t]*([A-Za-z\s]+)', l, flags=re.IGNORECASE)
                    if pob_m:
                        pob_cand = pob_m.group(1).split(',')[0].strip()
                        if pob_cand and not any(kw in pob_cand.upper() for kw in ["JENIS", "ALAMAT", "GOL", "NIK"]):
                            ktp_data["place_of_birth"] = pob_cand
                    elif i + 1 < len(lines):
                        pob_cand = lines[i+1].replace(',', '').strip()
                        if pob_cand and not any(c.isdigit() for c in pob_cand):
                            ktp_data["place_of_birth"] = pob_cand

        # 4. Gender
        if "LAKI-LAKI" in prompt.upper() or "LAKI" in prompt.upper():
            ktp_data["gender"] = "LAKI-LAKI"
        elif "PEREMPUAN" in prompt.upper():
            ktp_data["gender"] = "PEREMPUAN"

        # 5. Address
        addr_match = re.search(r'(\[ADDRESS_\d+\]|(?:Alamat|Address)\s*[:.-]?[ \t]*([^\n]+))', prompt, flags=re.IGNORECASE)
        if addr_match:
            address = addr_match.group(1).strip()
            address = re.sub(r'^(?:Alamat|Address)[:.;,\s-]*', '', address, flags=re.IGNORECASE).strip()
            address = re.sub(r'^[:;.,\s-]+', '', address).strip()
            address = re.sub(r'([A-Za-z]+)(IV|VI|VII|VIII|IX|X|III|II|I)', r'\1 \2 ', address, flags=re.IGNORECASE)
            address = re.sub(r'(IV|VI|VII|VIII|IX|X|III|II|I)(NO|NOMOR|\d+)', r'\1 \2 ', address, flags=re.IGNORECASE)
            address = re.sub(r'(NO|NOMOR)(\d+)', r'NO. \2', address, flags=re.IGNORECASE)
            address = re.sub(r'\bJL\b', 'JL.', address, flags=re.IGNORECASE)
            address = re.sub(r'\s+', ' ', address).strip()
            ktp_data["address"] = address

        # 6. RT/RW
        rtrw_match = re.search(r'(?:RT/RW|RT|RW)\s*[:.-]?[ \t]*([0-9/\s]+)', prompt, flags=re.IGNORECASE)
        if rtrw_match:
            ktp_data["rt_rw"] = re.sub(r'^[:;.,\s-]+', '', rtrw_match.group(1)).strip()

        # 7. Kel/Desa
        kel_match = re.search(r'(?:Kel/Desa|Kelurahan|Desa)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        if kel_match:
            kel_desa = kel_match.group(1).strip()
            kel_desa = re.sub(r'^(?:Kel/Desa|Kelurahan|Desa)[:.;,\s-]*', '', kel_desa, flags=re.IGNORECASE).strip()
            ktp_data["kel_desa"] = re.sub(r'^[:;.,\s-]+', '', kel_desa).strip()

        # 8. Kecamatan
        kec_match = re.search(r'(?:Kecamatan|Kec)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        if kec_match:
            kecamatan = kec_match.group(1).strip()
            kecamatan = re.sub(r'^(?:Kecamatan|Kec)[:.;,\s-]*', '', kecamatan, flags=re.IGNORECASE).strip()
            ktp_data["kecamatan"] = re.sub(r'^[:;.,\s-]+', '', kecamatan).strip()

        # 9. Religion
        rel_match = re.search(r'(?:Agama|Religion)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        rel_str = rel_match.group(1).strip().upper() if rel_match else prompt.upper()
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

        # 10. Marital Status
        mar_match = re.search(r'(?:Status Perkawinan|Perkawinan|Status)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        mar_str = mar_match.group(1).strip().upper() if mar_match else prompt.upper()
        if "BELUM" in mar_str:
            ktp_data["marital_status"] = "BELUM KAWIN"
        elif "KAWIN" in mar_str:
            ktp_data["marital_status"] = "KAWIN"

        # 11. Occupation
        occ_match = re.search(r'(?:Pekerjaan|Occupation)\s*[:.-]?[ \t]*([^\n]+)', prompt, flags=re.IGNORECASE)
        if occ_match:
            occ = occ_match.group(1).strip().upper()
            if "PELAJAR" in occ and "MAHASISWA" in occ:
                occ = "PELAJAR / MAHASISWA"
            elif "KARYAWAN" in occ and "SWASTA" in occ:
                occ = "KARYAWAN SWASTA"
            ktp_data["occupation"] = occ

        # Sanitize return fields
        for k, v in ktp_data.items():
            if isinstance(v, str):
                ktp_data[k] = self.sanitize_str(v)

        return ktp_data
