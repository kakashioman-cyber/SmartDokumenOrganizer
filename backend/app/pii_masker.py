import re
import json
import logging

logger = logging.getLogger("pii_masker")

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_REGEX = re.compile(
    r'\b(?:Telp|Tel|Phone|Handphone|HP|Mobile|Fax|T|P|F)\b[ \t]*[:.-]?[ \t]*(\+?\b\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{3,8}(?:[-.\s]?\d{3,8})?)|'
    r'\b(?:\+62|62|08)\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,5}\b|'
    r'\b\(0\d{2,3}\)[-.\s]?\d{6,8}\b',
    re.IGNORECASE
)
CREDIT_CARD_REGEX = re.compile(r'\b(?:\d{4}[-\s]){3}\d{4}\b')
NIK_REGEX = re.compile(r'\b\d{16}\b')
NPWP_REGEX = re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}\.?\d{1}-\d{3}\.?\d{3}\b')
PASSPORT_REGEX = re.compile(r'\b[A-Z]{1,2}\d{7,8}\b')

# Date of birth / Document Date regexes
DOB_REGEX = re.compile(
    r'\b(?:\d{1,2}[-./]\d{1,2}[-./](?:19|20)\d{2}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agu|Sep|Okt|Nov|Des|Januari|Februari|Maret|April|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)[a-z]*\s+(?:19|20)?\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b',
    re.IGNORECASE
)

# Address & RT/RW Regexes
ADDRESS_CONTEXT_REGEX = re.compile(
    r'\b(?:Alamat|Address)\s*[:.-]?[ \t]*([A-Za-z0-9\s.,/\\-]+?)(?=\s*(?:Tanggal|Tgl|Date|Nomor|No\.|Invoice|PO|Email|No\.\s*Telp|\||\n)|$)|'
    r'\b(?:JL\.?|JALAN)\s*[^\n|]+',
    re.IGNORECASE
)

PRICE_REGEX = re.compile(
    r'\b(?:Rp\.?|IDR|\$|€|£|USD|EUR)\s*\d+(?:[.,]\d+)*(?:\s*(?:USD|IDR|Rp\.?|EUR))?\b|'
    r'\b\d+(?:[.,]\d+)*\s*(?:USD|IDR|Rp\.?|EUR|SGD)\b',
    re.IGNORECASE
)

NAME_CONTEXT_REGEX = re.compile(
    r'\b(?:[Nn]ame|[Nn]ama|[Aa]ttn|[Aa]ttention|[Rr]ecipient|[Pp]enerima|[Ss]ender|[Pp]engirim|[Dd]ear|[Ss]incerely|[Yy]th|[Kk]epada|Invoice\s+for|Bill\s+to|Billed\s+to)\b[ \t]*[:.-]?[ \t]*\n?\s*([A-Za-z.]+(?:[ \t]+[A-Za-z.]+){0,4})',
    re.IGNORECASE
)

ORG_REGEX = re.compile(
    r'\b(?:PT|CV|Tbk|Ltd|Corp|Inc|LLC|Co|Company)[ \t]+[A-Z][A-Za-z0-9_]+(?:[ \t]+(?!(?:Nomor|Invoice|Tanggal|Alamat|Telp|Email|PO|Jalan|Jl)\b)[A-Z][A-Za-z0-9_]+)*|'
    r'\b[A-Z][A-Za-z0-9_]+(?:[ \t]+(?!(?:Nomor|Invoice|Tanggal|Alamat|Telp|Email|PO|Jalan|Jl)\b)[A-Z][A-Za-z0-9_]+)*[ \t]+(?:PT|CV|Tbk|Ltd|Corp|Inc|LLC|Co|Company)\b'
)

class PIIMasker:
    def __init__(self, enabled_types=None, custom_keywords=None):
        self.enabled_types = enabled_types or ['NAME', 'EMAIL', 'PHONE', 'ID', 'ORG', 'ADDRESS', 'DOB', 'CUSTOM']
        self.custom_keywords = [k.strip() for k in (custom_keywords or []) if k.strip()]
        self.clear()
        
    def clear(self):
        self.mask_map = {}
        self.unmask_map = {}
        self.counters = {}
        
    def _get_token(self, entity_type, original_value):
        val_clean = original_value.strip()
        if not val_clean:
            return original_value
            
        if val_clean in self.mask_map:
            return self.mask_map[val_clean]
            
        self.counters[entity_type] = self.counters.get(entity_type, 0) + 1
        idx = self.counters[entity_type]
        token = f"[{entity_type}_{idx}]"
        
        self.mask_map[val_clean] = token
        self.unmask_map[token] = val_clean
        return token

    def find_matches(self, text):
        matches = []
        if 'CUSTOM' in self.enabled_types and self.custom_keywords:
            for kw in self.custom_keywords:
                for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
                    matches.append({
                        'start': m.start(),
                        'end': m.end(),
                        'type': 'CUSTOM',
                        'value': m.group()
                    })

        if 'EMAIL' in self.enabled_types:
            for m in EMAIL_REGEX.finditer(text):
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'EMAIL',
                    'value': m.group()
                })

        if 'PHONE' in self.enabled_types:
            for m in PHONE_REGEX.finditer(text):
                val = m.group(1) if m.group(1) else m.group(0)
                val_clean = val.strip()
                if val_clean and not re.search(r'^\d{1,3}(?:\.\d{3})+$', val_clean):
                    start_pos = text.find(val_clean, m.start())
                    if start_pos != -1:
                        matches.append({
                            'start': start_pos,
                            'end': start_pos + len(val_clean),
                            'type': 'PHONE',
                            'value': val_clean
                        })

        if 'ID' in self.enabled_types:
            for m in CREDIT_CARD_REGEX.finditer(text):
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'CREDIT_CARD',
                    'value': m.group()
                })
            for m in NIK_REGEX.finditer(text):
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'NIK',
                    'value': m.group()
                })
            for m in NPWP_REGEX.finditer(text):
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'NPWP',
                    'value': m.group()
                })
            for m in PASSPORT_REGEX.finditer(text):
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'PASSPORT',
                    'value': m.group()
                })

        if 'DOB' in self.enabled_types:
            for m in DOB_REGEX.finditer(text):
                # Exempt business transaction dates (Submitted on, Invoice Date, Due Date, Order Date, Delivery Date, PO Date)
                pre_ctx = text[max(0, m.start() - 50):m.start()].upper()
                if any(kw in pre_ctx for kw in ["SUBMITTED ON", "INVOICE DATE", "INV. DATE", "INV DATE", "DATE OF INVOICE", "DUE DATE", "ORDER DATE", "DELIVERY DATE", "PO DATE", "PAYMENT TERM", "PAYMENT DATE", "JATUH TEMPO", "TANGGAL INVOICE", "TGL INVOICE", "TANGGAL BAYAR", "TGL BAYAR"]):
                    continue
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'DOB',
                    'value': m.group()
                })

        if 'ADDRESS' in self.enabled_types:
            for m in ADDRESS_CONTEXT_REGEX.finditer(text):
                val = m.group(1) if m.group(1) else m.group(0)
                val = re.sub(r'^(?:Alamat|Address)[:.;,\s-]*', '', val, flags=re.IGNORECASE).strip()
                if val:
                    start_pos = text.find(val, m.start())
                    if start_pos != -1:
                        matches.append({
                            'start': start_pos,
                            'end': start_pos + len(val),
                            'type': 'ADDRESS',
                            'value': val
                        })

        if 'PRICE' in self.enabled_types:
            for m in PRICE_REGEX.finditer(text):
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'PRICE',
                    'value': m.group()
                })

        if 'NAME' in self.enabled_types:
            for m in NAME_CONTEXT_REGEX.finditer(text):
                name_val = m.group(1).strip()
                if any(kw in name_val.upper() for kw in ["PAYABLE", "INVOICE", "ORDER", "SUBTOTAL", "TOTAL", "AMOUNT", "TEMPAT", "TEMPAL", "LAHIR", "TGL", "PROVINSI", "KOTA", "KABUPATEN", "AGAMA", "PEKERJAAN", "STATUS", "BERLAKU", "NIK", "GOL", "JENIS", "KELAMIN", "ALAMAT"]):
                    continue
                full_match = m.group()
                start_offset = full_match.index(name_val)
                # Dynamically strip any 3-letter ISO country code prefix (e.g. IDN, USA, SGP, MYS, DEU, etc.)
                iso_match = re.match(r'^([A-Z]{3})\s+', name_val, re.IGNORECASE)
                if iso_match:
                    prefix_len = len(iso_match.group(0))
                    name_val = name_val[prefix_len:].strip()
                    start_offset += prefix_len
                matches.append({
                    'start': m.start() + start_offset,
                    'end': m.start() + start_offset + len(name_val),
                    'type': 'NAME',
                    'value': name_val
                })

            # KTP Name Line Matcher (All-caps line between NIK and Nama/Tempat)
            lines_txt = text.split('\n')
            for idx, l_txt in enumerate(lines_txt):
                if 'NIK' in l_txt.upper() or re.search(r'\b\d{16}\b', l_txt):
                    for sub_l in lines_txt[idx+1 : idx+4]:
                        sub_c = sub_l.strip()
                        if sub_c and not any(kw in sub_c.upper() for kw in ['NIK', 'NAMA', 'PROVINSI', 'KOTA', 'KABUPATEN', 'TEMPAT', 'TEMPAL', 'LAHIR', 'TGL', 'AGAMA', 'GOL', 'JENIS', 'ALAMAT', 'RT', 'RW']):
                            if re.match(r'^[A-Za-z\s]{3,50}$', sub_c):
                                start_pos = text.find(sub_c)
                                if start_pos != -1:
                                    matches.append({
                                        'start': start_pos,
                                        'end': start_pos + len(sub_c),
                                        'type': 'NAME',
                                        'value': sub_c
                                    })
                                break

            # Also mask name segment inside Passport MRZ Line 1 e.g. P<IDN...
            mrz_name_regex = re.compile(r'P<[A-Z]{3}([A-Z<]{10,})', re.IGNORECASE)
            for m in mrz_name_regex.finditer(text):
                raw_name_seg = m.group(1)
                matches.append({
                    'start': m.start(1),
                    'end': m.end(1),
                    'type': 'NAME',
                    'value': raw_name_seg
                })

        if 'ORG' in self.enabled_types:
            for m in ORG_REGEX.finditer(text):
                matches.append({
                    'start': m.start(),
                    'end': m.end(),
                    'type': 'ORG',
                    'value': m.group()
                })
                
        return matches

    def _resolve_overlapping_matches(self, matches):
        sorted_matches = sorted(matches, key=lambda x: (x['start'], -(x['end'] - x['start'])))
        resolved = []
        last_end = -1
        
        for m in sorted_matches:
            if m['start'] >= last_end:
                resolved.append(m)
                last_end = m['end']
        return resolved

    def mask(self, text):
        if not text:
            return "", {}
            
        matches = self.find_matches(text)
        resolved_matches = self._resolve_overlapping_matches(matches)
        
        masked_text_parts = []
        last_idx = 0
        
        for m in resolved_matches:
            masked_text_parts.append(text[last_idx:m['start']])
            token = self._get_token(m['type'], m['value'])
            masked_text_parts.append(token)
            last_idx = m['end']
            
        masked_text_parts.append(text[last_idx:])
        return "".join(masked_text_parts), self.unmask_map

    def unmask(self, data):
        if isinstance(data, str):
            unmasked_str = data
            tokens = sorted(self.unmask_map.keys(), key=len, reverse=True)
            for token in tokens:
                unmasked_str = unmasked_str.replace(token, self.unmask_map[token])
            unmasked_str = re.sub(r'\[[A-Z_]+_\d+\]', 'N/A', unmasked_str)
            return unmasked_str
            
        elif isinstance(data, dict):
            return {self.unmask(k): self.unmask(v) for k, v in data.items()}
            
        elif isinstance(data, list):
            return [self.unmask(item) for item in data]
            
        return data

    def get_mask_summary(self):
        summary = []
        for token, original in sorted(self.unmask_map.items()):
            entity_type = token.strip("[]").split("_")[0]
            summary.append({
                "Token": token,
                "Type": entity_type,
                "Original": original
            })
        return summary
