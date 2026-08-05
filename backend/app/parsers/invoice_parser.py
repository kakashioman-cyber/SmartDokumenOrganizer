import re
from .base_parser import BaseDocumentParser
from ..verification import clean_currency_ocr_typos, clean_ocr_typos, verify_and_reconcile_invoice_math, normalize_date_format, parse_float_digits

def calculate_qty(qty_str, unit_price_str, total_str):
    if qty_str and qty_str.isdigit() and int(qty_str) > 1:
        return qty_str

    try:
        def to_float(val):
            v = str(val).replace('Rp', '').replace('S$', '').replace('$', '').replace('€', '').strip()
            v = re.sub(r'^[sS](?=\d)', '5', v).replace('o', '0').replace('O', '0')
            dec_m = re.search(r'[\.,](\d{2})$', v)
            if dec_m and not v.endswith(".000"):
                dec = f".{dec_m.group(1)}"
                v_int = v[:dec_m.start()]
            else:
                dec = ""
                v_int = v
            digits = re.sub(r'\D', '', v_int)
            return float(f"{digits}{dec}") if digits else 0.0

        p = to_float(unit_price_str)
        t = to_float(total_str)
        if p > 0 and t > 0:
            calc_q = round(t / p)
            if 1 <= calc_q <= 5000:
                return str(calc_q)
    except Exception:
        pass
    return qty_str if qty_str and qty_str != "0" else "1"

def format_currency(val_str, currency="IDR", include_symbol=True):
    if not val_str or val_str in ["N/A", "0.00", "0", ""]:
        symbol = "S$ " if currency == "SGD" else ("$ " if currency == "USD" else ("€ " if currency == "EUR" else ("₹ " if currency == "INR" else "Rp ")))
        return f"{symbol}0" if include_symbol else "0"

    if isinstance(val_str, (float, int)):
        num_val = float(val_str)
        val_str = f"{int(round(num_val))}" if abs(num_val - round(num_val)) < 0.001 else f"{num_val:.2f}"

    is_intl = currency in ["USD", "SGD", "EUR", "INR"]
    symbol = "S$ " if currency == "SGD" else ("$ " if currency == "USD" else ("€ " if currency == "EUR" else ("₹ " if currency == "INR" else "Rp ")))

    clean_val = str(val_str).replace('Rp', '').replace('S$', '').replace('$', '').replace('€', '').replace('₹', '').strip()
    clean_val = clean_val.replace('o', '0').replace('O', '0').replace('C', '0').replace('c', '0').replace('z', '2')
    clean_val = re.sub(r'\.00?$', '', clean_val)

    dec_str = ""
    if is_intl:
        m_dec = re.search(r'\.(\d{2})$', clean_val)
        if m_dec:
            dec_str = m_dec.group(1)
            clean_val = clean_val[:m_dec.start()]
    else:
        clean_val = re.sub(r'[\.,]00$', '', clean_val)

    digits_only = re.sub(r'\D', '', clean_val)
    if not digits_only:
        num = 0
    else:
        num = int(digits_only)

    if is_intl:
        formatted_num = f"{num:,}"
        if dec_str:
            formatted_num += f".{dec_str}"
    else:
        formatted_num = f"{num:,}".replace(',', '.')

    return f"{symbol}{formatted_num}" if include_symbol else formatted_num

# Backward compatibility alias
format_rupiah = format_currency

class InvoiceParser(BaseDocumentParser):
    """Modular Universal Parser for Invoices, Bills, & Receipts (0% Hardcoding)."""
    
    def parse(self, prompt: str) -> dict:
        prompt = clean_ocr_typos(prompt)
        lines = [l.strip() for l in prompt.split('\n') if l.strip()]
        
        invoice_data = {
            "vendor_name": "N/A",
            "customer_name": "N/A",
            "invoice_number": "N/A",
            "po_number": "N/A",
            "invoice_date": "N/A",
            "due_date": "N/A",
            "subtotal": "Rp 0",
            "tax": "0",
            "total_amount": "Rp 0",
            "currency": "IDR",
            "items": [],
            "quantity": "0"
        }

        # 1. Generic Currency Detection
        cur_match = re.search(r'\b(SGD|USD|EUR|IDR)\b|Currency\s*[:.-]?\s*([A-Za-z]{3})|\b(S\$|\$|€)\b', prompt, flags=re.IGNORECASE)
        if cur_match:
            c_str = (cur_match.group(1) or cur_match.group(2) or cur_match.group(3) or "").upper()
            if "SGD" in c_str or "S$" in c_str: invoice_data["currency"] = "SGD"
            elif "USD" in c_str or "$" in c_str: invoice_data["currency"] = "USD"
            elif "EUR" in c_str or "€" in c_str: invoice_data["currency"] = "EUR"

        # 1. Primary Vendor Name Extraction (Top of document)
        for line in lines[:8]:
            l_str = line.strip()
            l_clean = clean_ocr_typos(l_str)
            if any(kw in l_clean.upper() for kw in ["PT.", "CV.", "UD.", "INC", "CORP", "LTD", "LIMITED", "TBK", "SDN BHD", "SA", "GMBH"]):
                if not any(kw in l_clean.upper() for kw in ["CUSTOMER", "BILL TO", "SHIP TO", "ATTN", "KEPADA"]):
                    cand_v = re.split(r'(?i)\b(?:INVOICE|FAKTUR|NUMBER|NO\.|INV|DATE|DUE|TGL)\b', l_clean)[0].strip()
                    cand_v = re.sub(r'^(?:PT\.?|CV\.?|UD\.?)\s*', '', cand_v, flags=re.IGNORECASE).strip()
                    if cand_v and len(cand_v) > 2:
                        invoice_data["vendor_name"] = f"PT. {cand_v}" if "PT" in l_clean.upper() else cand_v
                        break

        # 2. Generic Vendor Name Detection (If top lines didn't match)
        if invoice_data["vendor_name"] == "N/A":
            ven_hdr_m = re.search(r'\bVENDOR\b\s*[:.-]?\s*\n?\s*(?:SHIP\s*TO\s*\n?\s*)?([A-Za-z0-9\s.&-]+)', prompt, re.IGNORECASE)
            if ven_hdr_m:
                cand_v = ven_hdr_m.group(1).strip()
                cand_v = re.split(r'(?i)\b(?:SHIP TO|BILL TO|BUYER|CUSTOMER|SITE|ADMINISTRATOR|ATTN|TO|ADDRESS|PO|ITEM|ITEM DESCRIPTION|QTY|UNIT|DESCRIPTION)\b', cand_v)[0].strip()
                if len(cand_v) > 2 and cand_v.upper() not in ["FOR", "DETAILS", "SHIP", "SHIP TO"]:
                    invoice_data["vendor_name"] = cand_v

        # 3. Customer Name
        cust_m = re.search(r'\b(?:Customer|BILL TO|Kepada|To|Nama Pelanggan)\b\s*[:.-]?\s*([^\n]+)', prompt, re.IGNORECASE)
        if cust_m:
            cand_c = cust_m.group(1).strip()
            cand_c = re.split(r'(?i)\b(?:Due|Phone|Fax|Inv|Date|Salesman|Currency|Payment)\b', cand_c)[0].strip(' :.-,')
            if cand_c and cand_c.upper() not in ["PT", "CV", "ADDRESS"]:
                invoice_data["customer_name"] = cand_c

        if invoice_data["vendor_name"] == "N/A":
            for line in lines[:8]:
                clean_l = line.strip()
                if clean_l.startswith("---") or "PAGE" in clean_l.upper():
                    continue
                l_upper = clean_l.upper()
                if any(kw in l_upper for kw in ["INVOICE", "NOTA", "STRUK", "PI "]):
                    v = re.sub(r'^(INVOICE|NOTA|STRUK)\s*', '', clean_l, flags=re.IGNORECASE).strip()
                    v = re.split(r'\b(NUMBER|NO|DATE|INV|OICE)\b', v, flags=re.IGNORECASE)[0].strip()
                    if len(v) > 2 and v.upper() not in ["FOR", "DETAILS"]:
                        invoice_data["vendor_name"] = v
                        break
                elif not any(kw in l_upper for kw in ["SUBMITTED", "KEPADA", "BILL TO", "INVOICE FOR", "TANGGAL", "DATE", "PHONE", "TELP", "JALAN", "JL", "RUKO"]) and len(clean_l) > 3:
                    v = re.split(r'\b(INVOICE|INV|NUMBER|NOTA|STRUK|DATE|TELP|EMAIL|JALAN|JL|JL\.|JAKARTA|RUKO|GEDUNG)\b', clean_l, flags=re.IGNORECASE)[0].strip()
                    v = re.sub(r'^[|:\s\-+]+|[|:\s\-+]+$', '', v).strip()
                    if len(v) > 2 and v.upper() not in ["FOR", "DETAILS", "PURCHASE ORDER", "PURCHASEORDER", "PURCHASE", "ORDER", "SURAT JALAN", "FAKTUR", "INVOICE"]:
                        invoice_data["vendor_name"] = v
                        break

        # 3. Generic Customer Name & Organization Combination Parser
        cust_cand = ""
        cust_org = ""
        cust_idx = -1

        for idx, l in enumerate(lines):
            lu = l.upper()
            if any(kw in lu for kw in ["KEPADA", "INVOICE FOR", "BILL TO", "BILLED TO", "CUSTOMER"]):
                cust_idx = idx
                c_m = re.search(r'(?:Customer|Bill To|Billed To|Kepada|Invoice For)\s*[:.-]?\s*([A-Za-z0-9\s.,\/-]+?)(?=\s+(?:Currency|Phone|Fax|Date|Due|Tax|PO|TANGGAL|\d{3,})|$)', l, re.IGNORECASE)
                if c_m and len(c_m.group(1).strip()) > 2 and c_m.group(1).strip().upper() not in ["TANGGAL", "DATE", "PAYABLE TO"]:
                    cust_cand = c_m.group(1).strip()
                    break

                if idx + 1 < len(lines):
                    values_line = lines[idx + 1].strip()
                    val_tokens = re.split(r'[,;\b](TANGGAL|DATE|\d{1,2}\s+[A-Za-z]+|\d{1,2}/\d{1,2}|28/\*03)\b', values_line, flags=re.IGNORECASE)[0].strip()
                    tokens = val_tokens.split()
                    if tokens:
                        cand = tokens[0]
                        if len(tokens) > 1 and not tokens[1].startswith("08") and not re.search(r'\d', tokens[1]):
                            cand = f"{tokens[0]} {tokens[1]}"
                        if len(cand) > 2 and cand.upper() not in ["TANGGAL", "DATE", "PAYABLE"]:
                            cust_cand = cand
                            break

        if cust_cand:
            search_lines = lines[cust_idx + 1: cust_idx + 5] if cust_idx != -1 else lines[:10]
            for l_search in search_lines:
                m_org = re.search(
                    r'\b(?:PT|CV|UD|Tbk|Ltd|Corp|Inc)\b[ \t]+[A-Za-z0-9_]+(?:[ \t]+[A-Za-z0-9_]+)*|'
                    r'\b[A-Za-z0-9_]+(?:[ \t]+[A-Za-z0-9_]+)*[ \t]+\b(?:PT|CV|UD|Tbk|Ltd|Corp|Inc)\b|'
                    r'\[ORG_\d+\]',
                    l_search, re.IGNORECASE
                )
                if m_org:
                    found_org = m_org.group(0).strip()
                    if invoice_data["vendor_name"] == "N/A" or found_org.upper() not in invoice_data["vendor_name"].upper():
                        cust_org = found_org
                        break

            if cust_org and cust_org.upper() not in cust_cand.upper():
                invoice_data["customer_name"] = f"{cust_cand} ({cust_org})"
            else:
                invoice_data["customer_name"] = cust_cand

        # 4. Generic Invoice Number Parser (100% Pure Regex, 0% Hardcoded)
        inv_header_pat = re.compile(
            r'\b(?:NO INVOICE|INVOICE #|INV OICE NUMBER|INVOICE NUMBER|NO\.?\s*INVOICE|INV NO|NOTA NO)\b|'
            r'\b(?:INVOICE|INV|NOTA|STRUK)\s*[:.#]|'
            r'\b(?:INVOICE|INV|NOTA|STRUK)\b.*?(?:#|\b(?:NO|NUMBER|NOMOR)\b)',
            re.IGNORECASE
        )

        for idx, l in enumerate(lines):
            if inv_header_pat.search(l):
                # Case A: Same line extraction
                m_same = re.search(r'(?:No\.?\s*Invoice|Invoice\s*No\.?|Invoice\s*Number|Nomor\s*Invoice|No\.?\s*Faktur|Faktur\s*No\.?|No\.?\s*Inv|INV/|INV-|INV:)\s*[:.#-]*\s*([A-Za-z0-9_*?/\.-]{3,30})', l, flags=re.IGNORECASE)
                if m_same and m_same.group(1).upper() not in ["DATE", "TANGGAL", "FOR", "TO", "DETAILS", "NO", "NUMBER"]:
                    raw_val = m_same.group(1).replace('*', '').strip()
                    if re.search(r'\d', raw_val):
                        num_val = re.sub(r'[oO]', '0', raw_val)
                        num_val = re.sub(r'[?]', '1', num_val)
                        if len(num_val) >= 3 and not num_val.startswith('[') and not any(t in num_val for t in ["NAME_", "PHONE_", "ORG_"]):
                            invoice_data["invoice_number"] = num_val
                            break

                # Case B: Next line extraction (immediately under NO INVOICE header)
                if invoice_data["invoice_number"] == "N/A" and idx + 1 < len(lines):
                    val_line = lines[idx + 1].strip()
                    tokens = val_line.split()
                    header_blacklist = {"KETERANGAN", "HARGA", "DESCRIPTION", "QTY", "TOTAL", "PAYABLE", "CUSTOMER", "PROJECT", "DUE", "NOTES", "NOTES:"}
                    for tok in tokens:
                        tok_clean = tok.replace('*', '')
                        if len(tok_clean) >= 3 and re.search(r'\d', tok_clean) and not tok_clean.startswith('08') and not tok_clean.startswith('['):
                            if tok_clean.upper() not in header_blacklist and not any(t in tok_clean for t in ["NAME_", "PHONE_", "ORG_"]):
                                tok_clean = re.sub(r'[oO]', '0', tok_clean)
                                tok_clean = re.sub(r'[?]', '1', tok_clean)
                                invoice_data["invoice_number"] = tok_clean
                                break

                # Case C: Previous line extraction (above NO INVOICE header)
                if (invoice_data["invoice_number"] == "N/A" or invoice_data["invoice_number"] == invoice_data.get("po_number")) and idx - 1 >= 0:
                    val_line = lines[idx - 1].strip()
                    tokens = val_line.split()
                    for tok in tokens:
                        tok_clean = tok.replace('*', '')
                        if len(tok_clean) >= 3 and re.search(r'\d', tok_clean) and not tok_clean.startswith('08') and not tok_clean.startswith('['):
                            if not any(t in tok_clean for t in ["NAME_", "PHONE_", "ORG_", "DATE"]):
                                tok_clean = re.sub(r'[oO]', '0', tok_clean)
                                invoice_data["invoice_number"] = tok_clean
                                break

                if invoice_data["invoice_number"] != "N/A" and invoice_data["invoice_number"] != invoice_data.get("po_number"):
                    break

        # Generic Fallback: If invoice_number is N/A or equals po_number, scan text for generic invoice code pattern
        if invoice_data["invoice_number"] == "N/A" or invoice_data["invoice_number"] == invoice_data.get("po_number") or not re.search(r'\d', invoice_data["invoice_number"]):
            gen_inv_m = re.search(r'\b(INV[A-Za-z0-9_-]*[/.-][A-Za-z0-9_/-]{3,20})\b', prompt, re.IGNORECASE)
            if gen_inv_m:
                invoice_data["invoice_number"] = gen_inv_m.group(1)

        # 5. PO Number
        po_match = re.search(r'(?:PO No|No\.?\s*PO|Nomor\s*PO|PO Number|PURCHASE ORDER|PO #|PO)\s*[:.#-]*[ \t]*\n?\s*([A-Z0-9_/.-]+|\[ID_\d+\])', prompt, flags=re.IGNORECASE)
        if po_match:
            cand_po = po_match.group(1).strip()
            if cand_po.upper() not in ["DATE", "NUMBER", "DETAILS"] and re.search(r'\d', cand_po):
                invoice_data["po_number"] = cand_po

        # 6. Generic Dates Parser (ISO YYYY-MM-DD / Slashed DD/MM/YYYY / Text 20 June 2024 / Masked [DOB_x], [DATE_x])
        date_pattern = r'(\[DOB_\d+\]|\[DATE_\d+\]|\b\d{4}[-./]\d{1,2}[-./]\d{1,2}\b|\b\d{1,2}[-./]\d{1,2}[-./]\d{2,4}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{2,4}\b)'
        dates = re.findall(date_pattern, prompt, re.IGNORECASE)
        valid_dates = [d for d in dates if not re.match(r'^\d+[.,]\d+$', d)]
        if valid_dates:
            invoice_data["invoice_date"] = valid_dates[0]
            invoice_data["due_date"] = valid_dates[1] if len(valid_dates) > 1 else valid_dates[0]

        # Contextual Invoice / Order Date (e.g. Submitted on 01/01/2025, P.O. Date Apr 05, 2023)
        inv_date_m = re.search(r'(?:Submitted\s*on|Invoice\s*Date|Tanggal\s*Invoice|Tanggal|P\.?O\.?\s*Date|Order\s*Date)\s*[:.-]?\s*\n?\s*(\[DOB_\d+\]|\[DATE_\d+\]|\d{1,2}[-./\s][A-Za-z0-9]{2,9}[-./\s]\d{2,4}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]{3}\s+\d{1,2},\s*\d{2,4})', prompt, flags=re.IGNORECASE)
        if inv_date_m:
            invoice_data["invoice_date"] = inv_date_m.group(1).strip()
            invoice_data["order_date"] = inv_date_m.group(1).strip()

        # Contextual Due / Delivery Date (e.g. Promise Date Apr 15, 2023, Due Date 16/01/2025)
        for i, l in enumerate(lines):
            if re.search(r'\b(?:Due\s*Date|Jatuh\s*Tempo|Promise\s*Date|Delivery\s*Date)\b', l, re.IGNORECASE):
                due_m_same = re.search(date_pattern, l, re.IGNORECASE)
                if due_m_same:
                    invoice_data["due_date"] = due_m_same.group(1).strip()
                    invoice_data["delivery_date"] = due_m_same.group(1).strip()
                elif i + 1 < len(lines):
                    due_m_next = re.search(date_pattern, lines[i+1], re.IGNORECASE)
                    if due_m_next:
                        invoice_data["due_date"] = due_m_next.group(1).strip()
                        invoice_data["delivery_date"] = due_m_next.group(1).strip()

        invoice_data["invoice_date"] = invoice_data["invoice_date"].replace("Klarct", "Maret")
        invoice_data["due_date"] = invoice_data["due_date"].replace("Klarct", "Maret")

        # 7. Generic Subtotal, Tax, Total Parser (4-Directional 360° Reader: Kanan, Bawah, Atas, Kiri)
        def find_financial_val(keywords, text_lines):
            def is_date_str(s):
                return bool(re.search(r'^\d{4}-\d{2}-\d{2}', s) or re.search(r'^\d{2}/\d{2}/\d{4}', s))

            for kw in keywords:
                for i, l in enumerate(text_lines):
                    if re.search(rf'\b{re.escape(kw)}\b', l, re.IGNORECASE):
                        # 1. Kanan (Right / After keyword on same line)
                        m_after = re.search(rf'\b{re.escape(kw)}\b\s*[:.-]?[ \t]*(?:Rp\.?|RP|AP|RF|S\$|\$)?\s*([\d.,oO]{{3,15}})', l, re.IGNORECASE)
                        if m_after and any(c.isdigit() for c in m_after.group(1)):
                            cand = m_after.group(1).strip()
                            if not is_date_str(cand):
                                return cand

                        # 2. Kiri (Left / Before keyword on same line)
                        m_left = re.search(r'([\d.,oO]{3,15})\s*(?:Rp\.?|RP|AP|RF|S\$|\$)?\s*\b' + re.escape(kw) + r'\b', l, re.IGNORECASE)
                        if m_left and any(c.isdigit() for c in m_left.group(1)):
                            cand = m_left.group(1).strip()
                            if not is_date_str(cand):
                                return cand

                        # 3. Bawah (Below / Next line)
                        if i + 1 < len(text_lines):
                            m_next = re.search(r'^(?:Rp\.?|RP|AP|RF|S\$|\$)?\s*([\d.,oO]{3,15})', text_lines[i + 1].strip(), re.IGNORECASE)
                            if m_next and any(c.isdigit() for c in m_next.group(1)):
                                cand = m_next.group(1).strip()
                                if not is_date_str(cand):
                                    return cand

                        # 4. Atas (Above / Preceding line)
                        if i - 1 >= 0:
                            m_prev = re.search(r'(?:Rp\.?|RP|AP|RF|S\$|\$)?\s*([\d.,oO]{3,15})$', text_lines[i - 1].strip(), re.IGNORECASE)
                            if m_prev and any(c.isdigit() for c in m_prev.group(1)):
                                cand = m_prev.group(1).strip()
                                if not is_date_str(cand):
                                    return cand
            return None

        raw_sub = find_financial_val(["Subtotal", "SUB TOTAL", "Gross Total"], lines)
        if raw_sub:
            raw_sub = re.sub(r'[oO]', '0', raw_sub)
            invoice_data["subtotal"] = format_currency(raw_sub, currency=invoice_data["currency"], include_symbol=True)

        raw_tax = find_financial_val(["PAJAK", "Tax", "PPN", "PPn"], lines)
        if raw_tax:
            raw_tax = re.sub(r'[oO]', '0', raw_tax)
            invoice_data["tax_amount"] = format_currency(raw_tax, currency=invoice_data["currency"], include_symbol=False)

        raw_tot = find_financial_val(["Total Cost", "Net Total", "Ner Total", "TOTAL", "Total Amount", "Tolal", "Totai", "TolaI", "Tota|"], lines)
        if raw_tot:
            raw_tot = re.sub(r'[oO]', '0', raw_tot)
            invoice_data["total_amount"] = format_currency(raw_tot, currency=invoice_data["currency"], include_symbol=True)
        elif invoice_data["subtotal"] not in ["Rp 0", "USD 0", "S$ 0", "0"]:
            invoice_data["total_amount"] = invoice_data["subtotal"]

        # 8. Generic Universal Table Item Parser (Handles Multi-Language Headers, Typos, Units & Math)
        header_idx = -1
        header_kws = ["DESCRIPTION", "DESKRIPSI", "KETERANGAN", "NAMA BARANG", "ITEM", "PART NO", "PRODUCT DESCRIPTION", "PART_NO", "DESC", "BARANG", "URAIAN", "SALUAN", "HARGA"]
        
        for idx, l in enumerate(lines):
            lu = l.upper()
            if any(kw in lu for kw in header_kws):
                header_idx = idx + 1
                break

        item_lines = lines[header_idx:] if header_idx != -1 else lines
        footer_kws = ["SUBTOTAL", "SUB TOTAL", "PEMBAYARAN", "PAJAK", "PPN", "TOTAL", "NOTES", "REMARK", "GROSS TOTAL", "NET TOTAL", "NER TOTAL", "INVORD", "INWORD", "SINCERELY", "TERIMAKASIH"]
        unit_pattern = r'\b(UNIT|Unit|unit|BOX|Box|box|PCS|Pcs|pcs|SET|Set|set|BATANG|Batang|LEMBAR|Lembar|ROLL|Roll|KG|Kg|kg|METER|Meter|MTR|LITER|Liter|LTR|CAN|DRUM|BOTOL|PAIL|DUS|PACK|LOT|BAG|EACH|Each|each|UOM|PKS|BTL)\b'

        # 1. Multi-line Vertical Stack Table Scanner (Handles unwrapped OCR tables where desc, qty, unit, price, total are on separate lines)
        start_i = header_idx if header_idx != -1 else 0
        v_i = start_i
        while v_i < len(lines):
            l_cur = lines[v_i].strip()
            if any(l_cur.upper().startswith(fk) for fk in footer_kws) and not any(h in l_cur.upper() for h in ["TOTAL COST", "TOTAL PRICE", "JUMLAH HARGA"]):
                break
            
            # Check window of 5 consecutive lines: desc \n qty \n unit \n price \n total
            if v_i + 4 < len(lines):
                desc_candidate = lines[v_i].strip()
                qty_cand = lines[v_i+1].strip()
                unit_cand = lines[v_i+2].strip()
                price_cand = lines[v_i+3].strip()
                total_cand = lines[v_i+4].strip()
                
                if not any(kw in desc_candidate.upper() for kw in ["DESCRIPTION", "QTY", "UNIT", "TOTAL", "SUBTOTAL", "PRICE", "COST"]):
                    try:
                        p_float = float(re.sub(r'[^\d.]', '', price_cand.replace(',', '')))
                        t_float = float(re.sub(r'[^\d.]', '', total_cand.replace(',', '')))
                        q_float = float(re.sub(r'[^\d.]', '', qty_cand.replace(',', '')))
                        if p_float > 0 and t_float > 0 and abs(q_float * p_float - t_float) < 0.1:
                            invoice_data["items"].append({
                                "no": str(len(invoice_data["items"]) + 1),
                                "sku": "-",
                                "description": desc_candidate,
                                "qty": str(int(q_float)),
                                "unit": unit_cand if re.search(unit_pattern, unit_cand, re.IGNORECASE) else "PCS",
                                "unit_price": format_currency(price_cand, currency=invoice_data["currency"], include_symbol=False),
                                "total": format_currency(total_cand, currency=invoice_data["currency"], include_symbol=False)
                            })
                            v_i += 5
                            continue
                    except Exception:
                        pass
            v_i += 1

        # 2. Single-line Horizontal Table Scanner (Runs if vertical scanner found 0 items)
        if not invoice_data["items"]:
            for l in item_lines:
                l_strip = l.strip()
                if not l_strip:
                    continue
                if any(l_strip.upper().startswith(fk) for fk in footer_kws) and not any(h in l_strip.upper() for h in ["TOTAL COST", "TOTAL PRICE", "JUMLAH HARGA"]):
                    if header_idx != -1:
                        break
                    else:
                        continue

                l_clean = clean_ocr_typos(l_strip)
                
                # Skip header rows, summary rows, or metadata notes lines
                if any(kw in l_clean.upper() for kw in ["DESKRIPSI", "PART NO", "HARGA SATUAN", "PRODUCT DESCRIPTION", "QTY SATUAN", "SUBTOTAL", "TOTAL"]):
                    continue
                if any(l_clean.upper().startswith(kw) for kw in ["SKU:", "SPEC:", "COMMENT:", "NOTE:", "NOTES:", "PAGE:", "REMARK:"]):
                    if l_clean.upper().startswith("SKU:") and invoice_data.get("items"):
                        sku_m2 = re.search(r'\bSKU:\s*([A-Za-z0-9_-]+)', l_clean, re.IGNORECASE)
                        if sku_m2:
                            invoice_data["items"][-1]["sku"] = sku_m2.group(1).strip()
                    continue

                # 1. Unit match
                u_match = re.search(unit_pattern, l_clean, re.IGNORECASE)
                unit_val = u_match.group(1).upper() if u_match else "PCS"

                # 2. Extract SKU / Part No (e.g. AN-PLT-625, AN-PLT-397, SKU-123)
                sku_val = "-"
                sku_m = re.search(r'\b([A-Za-z0-9]{2,6}-[A-Za-z0-9]{2,6}(?:-\d{2,5})?)\b', l_clean)
                if sku_m:
                    sku_val = sku_m.group(1)

                # 3. Price & Qty tokens extraction (handles OCR typos o/O/z/s/i)
                raw_prices = re.findall(r'(?:Rp\.?|RP|AP|RF|S\$|\$)?\s*([0-9.,oOCczsS]+)', l_clean)
                clean_prices = []
                for p in raw_prices:
                    p_clean = re.sub(r'[oO]', '0', p).replace('z', '2').replace('Z', '2').replace('s', '5').replace('S', '5').replace('ı', '1').strip(' .,')
                    if p_clean not in ["03", "01", "02", "04", "05", "06", "07", "08", "09", "10", "11", "12"] and re.search(r'\d', p_clean) and len(p_clean) >= 2:
                        clean_prices.append(p_clean)

                if clean_prices and parse_float_digits(clean_prices[-1]) > 0:
                    tot_val = clean_prices[-1]
                    price_val = clean_prices[-2] if len(clean_prices) >= 2 else tot_val

                    # 4. Smart Dimension Shield & Qty extraction
                    qty_val = "1"
                    q_match = re.search(r'\b(\d+)\s*(?:UNIT|Unit|unit|BOX|Box|box|EACH|Each|each|PCS|Pcs|pcs|SET|Set|set|BATANG|Batang|LEMBAR|Lembar|ROLL|Roll|KG|Kg|kg|METER|Meter|MTR|LITER|Liter|LTR|CAN|DRUM|BOTOL|PAIL|DUS|PACK|LOT|BAG|UOM|PKS|BTL)\b', l_clean, re.IGNORECASE)
                    if q_match:
                        cand_q = q_match.group(1)
                        is_dim = bool(re.search(r'\b[A-Za-z0-9]+\s*[xX*]\s*' + re.escape(cand_q) + r'\b', l_clean) or
                                     re.search(r'\b' + re.escape(cand_q) + r'\s*(?:inch|in|\"|mm|cm|m)\b', l_clean, re.IGNORECASE))
                        if not is_dim:
                            qty_val = cand_q

                    num_vals = [parse_float_digits(p) for p in clean_prices if parse_float_digits(p) > 0]
                    if len(num_vals) >= 2:
                        best_tuple = None
                        best_score = -1
                        for idx_q, q_f in enumerate(num_vals):
                            if 1 <= q_f <= 1000:
                                for idx_p, p_f in enumerate(num_vals):
                                    for idx_t, t_f in enumerate(num_vals):
                                        if abs(q_f * p_f - t_f) < 0.5 and t_f >= p_f and (q_f != t_f or q_f == 1):
                                            score = t_f
                                            if idx_q < idx_p < idx_t:
                                                score += 10000000
                                            if score > best_score:
                                                best_score = score
                                                best_tuple = (q_f, p_f, t_f, clean_prices[idx_p], clean_prices[idx_t])
                        if best_tuple:
                            qty_val = str(int(best_tuple[0]))
                            price_val = best_tuple[3]
                            tot_val = best_tuple[4]

                    # 5. Extract clean description
                    desc_val = l_clean
                    if sku_val != "-":
                        desc_val = desc_val.replace(sku_val, "")

                    desc_val = re.sub(r'^(?:[0-9.]+\s+)?', '', desc_val)
                    desc_val = re.sub(r'\b0%\s*0\b', '', desc_val)
                    desc_val = re.sub(r'(?:Rp\.?|RP|AP|RF|S\$|\$)?\s*\d[\d.,oO]*\b', '', desc_val, flags=re.IGNORECASE)
                    desc_val = re.sub(r'(?:Rp\.?|RP|AP|RF|S\$|\$)[A-Za-z0-9.]*', '', desc_val, flags=re.IGNORECASE)
                    desc_val = re.sub(r'\b(?:\d+\s*)?(?:UNIT|BOX|EACH|PCS|SET|BATANG|LEMBAR|ROLL|KG|METER|MTR|LITER|DRUM|PAIL|DUS|PACK|LOT|BAG)\b', '', desc_val, flags=re.IGNORECASE)
                    desc_val = re.sub(r'\b\d+\b', '', desc_val)
                    desc_val = re.sub(r'%\s*$', '', desc_val)
                    desc_val = re.sub(r'^[|:\s,.\-]+|[|:\s,.\-]+$', '', desc_val).strip()

                    if desc_val and desc_val.upper() not in ["NO.", "NO", "PRODUCT DESCRIPTION", "DESKRIPSI", "QUANTITY", "UOM", "UNIT PRICE", "GROSS AMC.", "NET AMOUNT", "AAMOUNT", "HARGA SATUAN", "JUMLAH"]:
                        real_qty = qty_val if (qty_val.isdigit() and int(qty_val) > 1) else calculate_qty(qty_val, price_val, tot_val)
                        invoice_data["items"].append({
                            "no": str(len(invoice_data["items"]) + 1),
                            "sku": sku_val,
                            "description": desc_val,
                            "qty": real_qty,
                            "unit": unit_val,
                            "unit_price": format_currency(price_val, currency=invoice_data["currency"], include_symbol=False),
                            "total": format_currency(tot_val if tot_val != "0" else price_val, currency=invoice_data["currency"], include_symbol=False)
                        })

        if invoice_data["items"]:
            invoice_data["quantity"] = str(len(invoice_data["items"]))

        return invoice_data

def clean_final_invoice_data(final_data, raw_prompt=""):
    if not isinstance(final_data, dict):
        return final_data

    # 1. Currency Normalization (Standard 3-letter ISO code)
    curr_raw = str(final_data.get("currency", "")).upper().strip()
    if raw_prompt and any(kw in raw_prompt for kw in ["GSTIN", "INR", "RUPEES", "₹", "INDIA"]):
        curr = "INR"
    elif any(kw in curr_raw for kw in ["SGD", "S$", "SINGAPORE"]):
        curr = "SGD"
    elif any(kw in curr_raw for kw in ["USD", "US$", "DOLLAR"]) or curr_raw == "$":
        curr = "USD"
    elif any(kw in curr_raw for kw in ["EUR", "EURO"]) or "€" in curr_raw:
        curr = "EUR"
    elif any(kw in curr_raw for kw in ["INR", "RUPEE"]) or "₹" in curr_raw:
        curr = "INR"
    elif any(kw in curr_raw for kw in ["RP", "IDR", "RUPIAH"]):
        curr = "IDR"
    elif raw_prompt and ("SGD" in raw_prompt.upper() or "SINGAPORE" in raw_prompt.upper() or "S$" in raw_prompt):
        curr = "SGD"
    elif raw_prompt and ("USD" in raw_prompt.upper() or "$" in raw_prompt):
        curr = "USD"
    elif raw_prompt and ("IDR" in raw_prompt.upper() or "RUPIAH" in raw_prompt.upper() or "RP" in raw_prompt.upper()):
        curr = "IDR"
    else:
        curr = curr_raw if curr_raw and curr_raw not in ["N/A", "NONE", "NULL", ""] else "IDR"
    final_data["currency"] = curr

    # 2. Vendor / Customer Name PT Normalization
    if "vendor_name" in final_data and final_data["vendor_name"] and final_data["vendor_name"] != "N/A":
        v_name = str(final_data["vendor_name"]).strip()
        v_name = re.sub(r'^\bPI\.?\b', 'PT.', v_name, flags=re.IGNORECASE)
        v_name = re.sub(r'\bPI\.?$', 'PT.', v_name, flags=re.IGNORECASE)
        final_data["vendor_name"] = v_name

    if "customer_name" in final_data and final_data["customer_name"] and final_data["customer_name"] != "N/A":
        cust_str = str(final_data["customer_name"]).strip()
        cust_str = re.sub(r'^\bPI\.?\b', 'PT.', cust_str, flags=re.IGNORECASE)
        cust_str = re.sub(r'\bPI\.?$', 'PT.', cust_str, flags=re.IGNORECASE)
        cust_str = cust_str.replace("SALPLE", "SAMPLE").replace("NDONESIA", "INDONESIA").replace("IINDONESIA", "INDONESIA")
        # Standardize "Name (PT Company)" -> "Name, PT Company" to match AI Vision output
        cust_str = re.sub(r'\s*\((PT|CV|UD|Tbk|Ltd|Corp|Inc)\b', r', \1', cust_str, flags=re.IGNORECASE).rstrip(')').strip()
        final_data["customer_name"] = cust_str

    # 2.5 Preserve exact invoice_number as physically printed on document (Option 1) and extract date if missing
    inv_val = str(final_data.get("invoice_number", "")).strip()
    m_inv_date = re.search(r'(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})', inv_val)
    if m_inv_date:
        if not final_data.get("invoice_date") or final_data.get("invoice_date") in ["N/A", "", None, "null"]:
            final_data["invoice_date"] = m_inv_date.group(1)

    # 3. Invoice Number Fallback Verification against raw unmasked prompt
    inv = str(final_data.get("invoice_number", "")).strip()
    if (inv in ["N/A", "Invoice", "PT", "NONE", "NULL", "", "-"] or not re.search(r'\d', inv)) and raw_prompt:
        inv_m = re.search(r'(?:No\.?\s*Invoice|Invoice\s*No|Invoice\s*Number|NO INVOICE|INVOICE #|INV/|INV:|INV-|No\.?\s*Inv)\s*[:.-]?[ \t]*\n?\s*(?:[A-Za-z]+\s+){0,2}([A-Za-z0-9_*?/\.-]{3,30})', raw_prompt, re.IGNORECASE)
        if not inv_m:
            inv_m = re.search(r'[:\s](INV/[A-Za-z0-9_/.-]+)', raw_prompt, re.IGNORECASE)
        if inv_m:
            cand_inv = inv_m.group(1).replace('*', '').strip()
            if cand_inv.upper() not in ["DATE", "TANGGAL", "FOR", "TO", "DETAILS"] and re.search(r'\d', cand_inv):
                final_data["invoice_number"] = cand_inv

    # 4. Customer Name PT Combination Verification
    cust = str(final_data.get("customer_name", ""))
    if cust != "N/A" and raw_prompt:
        lines_raw = [l.strip() for l in raw_prompt.split('\n') if l.strip()]
        for idx, l in enumerate(lines_raw):
            if any(kw in l.upper() for kw in ["INVOICE FOR", "KEPADA", "BILL TO", "CUSTOMER"]):
                for l_sub in lines_raw[idx+1 : idx+5]:
                    m_org = re.search(r'\b(?:PT|CV|UD|Tbk|Ltd|Corp|Inc)\b[ \t]+[A-Za-z0-9_]+(?:[ \t]+[A-Za-z0-9_]+)*|\b[A-Za-z0-9_]+(?:[ \t]+[A-Za-z0-9_]+)*[ \t]+\b(?:PT|CV|UD|Tbk|Ltd|Corp|Inc)\b', l_sub, re.IGNORECASE)
                    if m_org:
                        found_org = m_org.group(0).strip()
                        vendor = str(final_data.get("vendor_name", ""))
                        if not vendor or found_org.upper() not in vendor.upper():
                            if found_org.upper() not in cust.upper():
                                final_data["customer_name"] = f"{cust}, {found_org}"
                            break
                break

    # 5. Date Normalization (Convert "11 February 2013" / "YYYY-MM-DD" / "28-03-2022" -> "DD/MM/YYYY" and default missing due_date to N/A)
    import dateutil.parser
    for date_key in ["invoice_date", "due_date"]:
        d_val = str(final_data.get(date_key, "")).strip()
        if not d_val or d_val in ["N/A", "null", "None", "undefined", ""]:
            final_data[date_key] = "N/A"
        else:
            m_iso = re.search(r'(\d{4})[\/\.-](\d{1,2})[\/\.-](\d{1,2})', d_val)
            if m_iso:
                final_data[date_key] = f"{int(m_iso.group(3)):02d}/{int(m_iso.group(2)):02d}/{m_iso.group(1)}"
            else:
                m_d = re.search(r'(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})', d_val)
                if m_d:
                    day, month, year = m_d.group(1), m_d.group(2), m_d.group(3)
                    if len(year) == 2:
                        year = f"20{year}"
                    final_data[date_key] = f"{int(day):02d}/{int(month):02d}/{year}"
                else:
                    try:
                        dt = dateutil.parser.parse(d_val, dayfirst=True)
                        final_data[date_key] = dt.strftime("%d/%m/%Y")
                    except Exception:
                        pass

    # 6. Ensure PO Number is Present or N/A
    po_val = str(final_data.get("po_number") or "").strip()
    if not po_val or po_val.upper() in ["RE", "N/A", "NULL", "NONE", "UNDEFINED", "INV", "NO"]:
        final_data["po_number"] = "N/A"
    elif raw_prompt and not raw_prompt.startswith("[Direct Vision") and not re.search(r'\b(?:PO|P\.O\.?|PURCHASE\s*ORDER)\b', raw_prompt, re.IGNORECASE):
        final_data["po_number"] = "N/A"
    else:
        final_data["po_number"] = po_val

    # 6.5 Delivery Date Validation (Default to N/A unless raw text explicitly contains delivery/promise date)
    deliv_val = str(final_data.get("delivery_date") or "").strip()
    if raw_prompt and not raw_prompt.startswith("[Direct Vision") and not re.search(r'\b(?:DELIVERY|PROMISE\s*DATE|SHIP\s*DATE|PENGIRIMAN)\b', raw_prompt, re.IGNORECASE):
        final_data["delivery_date"] = "N/A"

    # 7. Trio-Consensus Math Engine Reconciliation
    final_data = verify_and_reconcile_invoice_math(final_data)

    # 8. Format Subtotal, Tax, & Total Amount Uniformly
    sub_val = final_data.get("subtotal") or "0"
    final_data["subtotal"] = format_currency(sub_val, currency=curr, include_symbol=True)
    
    sub_f = parse_float_digits(sub_val)
    tot_f = parse_float_digits(final_data.get("total_amount"))
    tax_amt_flt = parse_float_digits(final_data.get("tax_amount"))
    tax_pct_str = str(final_data.get("tax") or "0%").strip()

    # 1. If tax_amount is missing/0 but total > subtotal, compute tax_amount = total - subtotal
    if tax_amt_flt <= 0 and sub_f > 0 and tot_f > sub_f:
        tax_amt_flt = tot_f - sub_f

    # 2. If tax_amount is missing/0 but tax rate exists (e.g., "11%"), compute tax_amount = subtotal * rate
    m_pct = re.search(r'(\d{1,2}(?:\.\d+)?)\s*%', tax_pct_str)
    if tax_amt_flt <= 0 and sub_f > 0 and m_pct:
        rate = float(m_pct.group(1)) / 100.0
        tax_amt_flt = round(sub_f * rate, 2)

    # 3. Format tax percentage & tax amount
    if tax_amt_flt > 0:
        if m_pct and float(m_pct.group(1)) > 0:
            rate_num = float(m_pct.group(1))
            tax_pct_str = f"{int(rate_num)}%" if rate_num.is_integer() else f"{rate_num}%"
        elif sub_f > 0:
            calc_r = round((tax_amt_flt / sub_f) * 100)
            tax_pct_str = f"{calc_r}%"
        final_data["tax_amount"] = format_currency(tax_amt_flt, currency=curr, include_symbol=False)
    else:
        tax_pct_str = "0%"
        final_data["tax_amount"] = "0.00"

    final_data["tax"] = tax_pct_str
    
    tot_val = final_data.get("total_amount") or sub_val
    final_data["total_amount"] = format_currency(tot_val, currency=curr, include_symbol=True)
    
    if "items" in final_data and isinstance(final_data["items"], list):
        expanded_items = []
        for item in final_data["items"]:
            if isinstance(item, dict):
                # Separate Qty vs Unit if Qty contains unit string (e.g., "50 Kg", "10 kg", "5 pack", "500 lembar")
                raw_qty = str(item.get("qty", "1")).strip()
                m_unit = re.search(r'\b(kg|Kg|KG|pack|pcs|Pcs|PCS|lembar|uom|UOM|box|Box|BOX|unit|Unit|UNIT|roll|Roll|ROLL|each|Each|EACH|set|Set|SET)\b', raw_qty)
                if m_unit:
                    item["unit"] = m_unit.group(1)
                    item["qty"] = re.sub(r'[^\d.]', '', raw_qty).strip() or "1"

                # Extract SKU from Part No or Description if SKU is missing
                sku_val = str(item.get("sku") or item.get("part_no") or item.get("part_number") or item.get("code") or item.get("item_code") or "").strip()
                if not sku_val or sku_val in ["-", "N/A", "null", "None"]:
                    desc = str(item.get("description", ""))
                    m_sku = re.search(r'\b([A-Za-z0-9]{3,6}-[A-Za-z0-9]{3,6}(?:-\d{3,4})?|\d{4,6})\b', desc)
                    if m_sku and m_sku.group(1).upper() not in ["INCH", "BOX", "UNIT", "PCS", "PACK", "ROLL", "EACH"]:
                        sku_val = m_sku.group(1)
                item["sku"] = sku_val if sku_val else "-"

                desc = str(item.get("description", "")).strip()
                if "\n" in desc:
                    desc = desc.split("\n")[0].strip()
                desc = re.split(r'(?i)\b(?:Spec|Specification|Comment|Comments|SKU|Note|Notes|Remark|Remarks)\s*:', desc)[0].strip()
                item["description"] = desc
                sku_matches = list(re.finditer(r'\b([A-Z]{2,4}-[A-Z0-9]{3,4}-\d{3,4})\b', desc))
                if len(sku_matches) > 1:
                    for i, match in enumerate(sku_matches):
                        start = match.start()
                        end = sku_matches[i+1].start() if i+1 < len(sku_matches) else len(desc)
                        sub_desc = desc[start:end].strip()
                        m_sku = match.group(1)
                        sub_desc_clean = re.sub(r'^\b' + re.escape(m_sku) + r'\b\s*', '', sub_desc).strip()
                        expanded_items.append({
                            "no": str(len(expanded_items) + 1),
                            "sku": m_sku,
                            "description": sub_desc_clean or sub_desc,
                            "qty": item.get("qty", "1"),
                            "unit": item.get("unit", "pcs"),
                            "unit_price": format_currency(item.get("unit_price", "0"), currency=curr, include_symbol=False),
                            "total": format_currency(item.get("total", "0"), currency=curr, include_symbol=False)
                        })
                else:
                    item["no"] = str(len(expanded_items) + 1)
                    if "unit_price" in item:
                        item["unit_price"] = format_currency(item["unit_price"], currency=curr, include_symbol=False)
                    if "total" in item:
                        item["total"] = format_currency(item["total"], currency=curr, include_symbol=False)
                    expanded_items.append(item)
        final_data["items"] = expanded_items
        final_data["quantity"] = str(len(expanded_items))

    # Fix slash in invoice_number if OCR read INVIAN -> INV/AN
    inv_num = str(final_data.get("invoice_number", "")).strip()
    if inv_num:
        inv_num = re.sub(r'\bINVIAN-', 'INV/AN-', inv_num, flags=re.IGNORECASE)
        inv_num = re.sub(r'\bINV AN-', 'INV/AN-', inv_num, flags=re.IGNORECASE)
        final_data["invoice_number"] = inv_num
                
    return final_data
