import re
from .base_parser import BaseDocumentParser
from .invoice_parser import clean_ocr_typos

class VendorDocumentParser(BaseDocumentParser):
    """Modular Parser for Procurement & Vendor Documents (Dokumen Pengadaan / Vendor / Surat Jalan)."""
    
    def parse(self, prompt: str) -> dict:
        prompt = clean_ocr_typos(prompt)
        lines = [l.strip() for l in prompt.split('\n') if l.strip()]

        from .invoice_parser import InvoiceParser
        inv_parser = InvoiceParser()
        base_data = inv_parser.parse(prompt)

        vendor_data = {
            "vendor_name": base_data.get("vendor_name", "N/A"),
            "customer_name": base_data.get("customer_name", "N/A"),
            "po_number": base_data.get("po_number", "N/A"),
            "invoice_number": base_data.get("invoice_number", "N/A"),
            "delivery_order_number": "N/A",
            "invoice_date": base_data.get("invoice_date", "N/A"),
            "due_date": base_data.get("due_date", "N/A"),
            "order_date": base_data.get("invoice_date", "N/A"),
            "delivery_date": "N/A",
            "item_name": "N/A",
            "quantity": "N/A",
            "unit_price": "N/A",
            "subtotal": base_data.get("subtotal", "0"),
            "tax": base_data.get("tax", "0"),
            "tax_amount": base_data.get("tax", "0"),
            "total_amount": base_data.get("total_amount", "0"),
            "currency": base_data.get("currency", "IDR"),
            "payment_terms": "N/A",
            "items": base_data.get("items", [])
        }

        # 1. Universal 2-Column Header Splitter (e.g. VENDOR [col 1] SHIP TO [col 2] -> Staples [col 1] Procurify [col 2])
        v_name = "N/A"
        c_name = "N/A"

        sup_m = re.search(r'(?:Supplier\s*Name|Supplier|Vendor\s*Name|Vendor|Penyedia|Invoice\s*From)\s*[:.-]?\s*([^\n\r|]+)', prompt, re.IGNORECASE)
        if sup_m:
            v_cand = sup_m.group(1).strip()
            v_cand = re.split(r'\b(?:Supplier\s*Code|VNDR|Address|GSTIN|PO\s*No|Jalan|Jl|Phone|Telp|Fax)\b', v_cand, flags=re.IGNORECASE)[0].strip()
            v_cand = re.sub(r'[:.-]+$', '', v_cand).strip()
            if v_cand and v_cand.upper() not in ["N/A", "NULL", "NONE"]:
                v_name = v_cand

        for idx_col, l_col in enumerate(lines[:20]):
            if re.search(r'\bVENDOR\b.*\b(?:SHIP|BILL)\b', l_col, re.IGNORECASE) and idx_col + 1 < len(lines):
                val_line = lines[idx_col + 1].strip()
                tokens = val_line.split()
                if len(tokens) >= 2:
                    v_name = tokens[0]
                    c_name = tokens[1]
                    break
                elif len(tokens) == 1:
                    v_name = tokens[0]

        # 2. Customer Name (Buyer / Bill To / Ship To / Header / Masked PII Tag)
        if c_name == "N/A":
            bill_block = re.search(r'BILL\s+TO\s*\n?([\s\S]{1,200}?)(?=\bVENDOR\b|\bSHIP\s+TO\b|\bITEM\b|\bPURCHASE\b|$)', prompt, re.IGNORECASE)
            if bill_block:
                lines_b = [l.strip() for l in bill_block.group(1).split('\n') if l.strip()]
                for l_b in lines_b:
                    if not re.search(r'\b(?:Shipping|Methods|FOB|Payment|Terms|Net|Promise|Date|Address|Contact|Email|Phone|Fax|PO|No)\b', l_b, re.IGNORECASE):
                        c_name = l_b
                        break

        if c_name == "N/A":
            bill_m = re.search(r'(?:Bill\s*To|Ship\s*To|Customer\s*Name|Customer|Buyer|Kepada|Penerima)\s*[:.-]?[ \t]*\n?\s*([^\n|]+)', prompt, re.IGNORECASE)
            if bill_m:
                c_cand = bill_m.group(1).strip()
                c_cand = re.sub(r'[:.-]+$', '', c_cand).strip()
                if c_cand and len(c_cand) > 1 and not re.match(r'^(?:Address|Contact|Email|GSTIN|Phone|Telp|Fax|PO|Date|No|---)\b', c_cand, re.IGNORECASE):
                    c_name = c_cand

        # 3. High-Precision Vendor / Supplier Name Search
        if v_name == "N/A":
            org_m = re.search(r'\b(?:PT|CV|UD|Tbk|Ltd|Corp|Inc|Store|Shop)\b[ \t]+[A-Za-z0-9_\s.-]+', prompt, re.IGNORECASE)
            if org_m:
                cand_org = org_m.group(0).strip()
                cand_org = re.split(r'[\n|]', cand_org)[0].strip()
                cand_org = re.split(r'\b(?:Invoice|PO|No|Tanggal|Mata Uang)\b', cand_org, flags=re.IGNORECASE)[0].strip()
                v_name = re.sub(r'[:.-]+$', '', cand_org).strip()

        if v_name == "N/A":
            v_block = re.search(r'VENDOR(?:\s+SHIP\s+TO)?\s*\n?([\s\S]{1,200}?)(?=\bBILL\s+TO\b|\bSHIP\s+TO\b|\bITEM\b|\bPURCHASE\b|$)', prompt, re.IGNORECASE)
            if v_block:
                lines_v = [l.strip() for l in v_block.group(1).split('\n') if l.strip()]
                for l_v in lines_v:
                    l_v_clean = re.sub(r'^(?:VENDOR|SUPPLIER|SHIP\s+TO|BILL\s+TO)\s*', '', l_v, flags=re.IGNORECASE).strip()
                    if l_v_clean and not re.search(r'\b(?:Site|Administrator|PO\s*Box|Manager|Address|Phone|Telp|Fax)\b', l_v_clean, re.IGNORECASE):
                        if c_name != "N/A" and c_name.upper() in l_v_clean.upper():
                            l_v_clean = re.sub(re.escape(c_name), '', l_v_clean, flags=re.IGNORECASE).strip()
                        v_name = l_v_clean
                        break

        if v_name == "N/A":
            sup_m2 = re.search(r'(?:Supplier\s*Name|Supplier|Vendor\s*Name|Vendor|Penyedia|Invoice\s*From)\s*[:.-]?[ \t]*(\[NAME_\d+\]|\[ORG_\d+\]|[A-Za-z0-9\s._-]+)', prompt, re.IGNORECASE)
            if sup_m2:
                cand = sup_m2.group(1).strip()
                cand = re.split(r'\b(?:Supplier\s*Code|VNDR|Address|GSTIN|PO\s*No|Jalan|Jl|Phone|Telp|Fax)\b', cand, flags=re.IGNORECASE)[0].strip()
                v_name = re.sub(r'[:.-]+$', '', cand).strip()

        if v_name == "N/A":
            for l in lines[:5]:
                if not re.search(r'(?:Supplier|Vendor|Address|Contact|Email|Phone|GSTIN|PO|Invoice|Date|Tanggal|Page|Halaman|Qty|Satuan|Harga|Jumlah|Part\s*No|Deskripsi|---)', l, re.IGNORECASE):
                    clean_l = re.split(r'[:\s]+(?:PO|INV|No|Tanggal)\b', l, flags=re.IGNORECASE)[0].strip()
                    clean_l = re.sub(r'[:.-]+$', '', clean_l).strip()
                    if len(clean_l) > 2 and not clean_l.isdigit():
                        v_name = clean_l
                        break

        if v_name != "N/A" and v_name.upper() not in ["PURCHASE ORDER", "PURCHASEORDER", "INVOICE", "SURAT JALAN"]:
            vendor_data["vendor_name"] = v_name
        if c_name != "N/A" and "---" not in c_name and "Page" not in c_name:
            c_name = re.sub(r'^(?:PURCHASE\s*ORDER|PURCHASEORDER)\s*', '', c_name, flags=re.IGNORECASE).strip()
            if c_name:
                vendor_data["customer_name"] = c_name

        # 4. High-Precision PO Number & Invoice Number Search
        po_num = "N/A"
        po_match = re.search(r'(?:PO No|No\.?\s*PO|Nomor\s*PO|PO Number|PO Number:|PO\s*#|PO\s*-\s*\d+|PURCHASE ORDER\s*#?)\s*[:.#-]*[ \t]*([A-Z0-9_/.-]{1,30})', prompt, flags=re.IGNORECASE)
        if not po_match:
            po_match = re.search(r'[:\s](PO-[A-Z0-9_-]+)', prompt, flags=re.IGNORECASE)
        if po_match:
            cand_po = po_match.group(1).strip().replace('*', '')
            if cand_po.upper() not in ["DATE", "NUMBER", "DETAILS"] and re.search(r'\d', cand_po):
                po_num = cand_po

        inv_num = base_data.get("invoice_number", "N/A")
        inv_m = re.search(r'(?:No\.?\s*Invoice|Invoice\s*No\.?|Invoice\s*Number|Nomor\s*Invoice|No\.?\s*Faktur|Faktur\s*No\.?|No\.?\s*Inv|INV/|INV-|INV:)\s*[:.#-]*\s*([A-Za-z0-9_*?/\.-]{3,30})', prompt, flags=re.IGNORECASE)
        if not inv_m:
            inv_m = re.search(r'[:\s](INV/[A-Z0-9_/.-]+)', prompt, flags=re.IGNORECASE)
        if inv_m:
            cand_inv = inv_m.group(1).strip().replace('*', '')
            if cand_inv.upper() not in ["DATE", "TANGGAL", "NUMBER", "DETAILS"] and re.search(r'\d', cand_inv):
                inv_num = cand_inv

        if 'INV' in po_num and 'PO' in inv_num:
            po_num, inv_num = inv_num, po_num
        elif 'INV' in po_num and ('PO' not in inv_num and inv_num != "N/A"):
            inv_num = po_num
            po_match2 = re.search(r'[:\s](PO-[A-Z0-9_-]+)', prompt, flags=re.IGNORECASE)
            po_num = po_match2.group(1) if po_match2 else "N/A"

        if inv_num != "N/A" and re.search(r'^PO[-_]', inv_num, re.IGNORECASE):
            inv_num = "N/A"

        if po_num != "N/A": vendor_data["po_number"] = po_num
        if inv_num != "N/A": vendor_data["invoice_number"] = inv_num

        # 5. Delivery Order Number (Surat Jalan / DO No)
        do_match = re.search(r'(?:Surat Jalan|DO No|No\.?\s*Surat Jalan|No\.?\s*DO|Delivery Order|DO #|DO\s*[:.-])\s*[:.-]?[ \t]*([A-Z0-9_*?/\.-]{3,30})', prompt, flags=re.IGNORECASE)
        if do_match:
            vendor_data["delivery_order_number"] = do_match.group(1).strip().replace('*', '')

        # 6. Dates: Order Date & Delivery / Arrival Date
        date_pattern = r'([A-Za-z]{3}\s+\d{1,2},?\s+\d{4}|\d{1,2}[-./\s][A-Za-z0-9]{2,9}[-./\s]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\[DOB_\d+\]|\[DATE_\d+\])'
        deliv_date_match = re.search(r'(?:Delivery Date|Promise Date|Pramise Date|Tgl\.?\s*Datang|Tanggal\s*Datang|Tgl\.?\s*Kirim|Tanggal\s*Pengiriman|Arrival Date|Tgl\.?\s*Penerimaan)\s*[:.-]?[ \t]*' + date_pattern, prompt, flags=re.IGNORECASE)
        if deliv_date_match:
            vendor_data["delivery_date"] = deliv_date_match.group(1).strip()

        order_date_match = re.search(r'(?:Order Date|PO\.?\s*Date|Tgl\.?\s*Pesan|Tanggal\s*Pesan|Tanggal\s*PO|PO Date|Tanggal|Tgl)\s*[:.-]?[ \t]*' + date_pattern, prompt, flags=re.IGNORECASE)
        if order_date_match:
            vendor_data["order_date"] = order_date_match.group(1).strip()

        # 7. Tax Rate & Tax Amount
        tax_rate = "0%"
        tax_amt = "0.00"
        ppn_m = re.search(r'\b(?:PPN|VAT|TAX|GST)\s*(?:\(\s*(\d+(?:\.\d+)?%?)\s*\))?', prompt, re.IGNORECASE)
        if ppn_m and ppn_m.group(1):
            tax_rate = ppn_m.group(1).strip()
            if not tax_rate.endswith('%'):
                tax_rate += '%'

        ppn_amt_m = re.search(r'\b(?:PPN|VAT|TAX|GST)\s*(?:\(\s*\d+(?:\.\d+)?%?\s*\))?\s*[:.-]?\s*([0-9.,]+)', prompt, re.IGNORECASE)
        if ppn_amt_m:
            tax_amt = ppn_amt_m.group(1).strip()

        vendor_data["tax"] = tax_rate
        vendor_data["tax_amount"] = tax_amt

        # 8. Financial Totals (Subtotal, Discounts, Grand Total)
        sub_m = re.search(r'\bSubtotal\s*[:.-]?\s*([\d.,]{3,15})', prompt, re.IGNORECASE)
        if not sub_m:
            sub_m = re.search(r'^\s*Total\s+([\d.,]{3,15})', prompt, re.MULTILINE | re.IGNORECASE)
        if sub_m:
            vendor_data["subtotal"] = sub_m.group(1).strip()

        disc_m = re.search(r'\bDiscounts?\s*[:.-]?\s*([\d.,]+)', prompt, re.IGNORECASE)
        if disc_m:
            vendor_data["discount"] = disc_m.group(1).strip()

        gtot_m = re.search(r'\b(?:Grand\s*Total|Total\s*Cost|Total\s*Amount|Jumlah\s*Total)\s*[:.-]?\s*([0-9.,]{1,12})', prompt, re.IGNORECASE)
        if gtot_m:
            vendor_data["total_amount"] = gtot_m.group(1).strip()
        elif vendor_data.get("discount") and vendor_data.get("subtotal"):
            s_f = parse_float_digits(vendor_data["subtotal"])
            d_f = parse_float_digits(vendor_data["discount"])
            if s_f > d_f > 0:
                vendor_data["total_amount"] = str(round(s_f - d_f, 2))

        # 9. Header-Bounded SKU Table Parser with Line-Usage Tracking & Math Candidate Filtering
        from ..verification import parse_float_digits
        def fmt_num(n):
            return f"{int(round(n)):,}".replace(',', '.') if n >= 1000 else str(int(round(n)))

        header_i = 0
        for i, l in enumerate(lines):
            if any(kw in l.upper() for kw in ['PART NO', 'DESKRIPSI', 'QTY', 'SATUAN', 'HARGA SATUAN', 'JUMLAH']):
                header_i = i
                break

        sku_rows = []
        for idx, l in enumerate(lines):
            if idx <= header_i:
                continue
            m = re.search(r'\b(?!\d{4}-\d{2}-\d{2}\b)(?!\d{2}-\d{2}-\d{4}\b)([A-Z0-9]{2,6}-[A-Z0-9]{2,6}-\d{2,4})\b', l)
            if m:
                sku_rows.append((idx, m.group(1)))

        all_skus = [s[1] for s in sku_rows]
        parsed_items = []
        used_line_indices = set()

        def clean_line_for_dim_nums(txt):
            c = re.sub(r'^\s*\d+[\s.]+', '', txt.strip())
            for s_item in all_skus:
                c = c.replace(s_item, '')
            c = re.sub(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b', '', c)
            c = re.sub(r'\b\d+\s*(?:inch|in|mm|cm|m)\b', '', c, flags=re.IGNORECASE)
            c = re.sub(r'\bM\d+\b|\b\d+\s*[×x*]\s*\d+\b', '', c, flags=re.IGNORECASE)
            return c

        footer_i = len(lines)
        for i, l in enumerate(lines):
            if i > header_i and any(kw in l.upper() for kw in ['SUBTOTAL', 'PPN', 'TOTAL', 'TAX', 'VAT', 'AMOUNT DUE', 'BALANCE DUE']):
                footer_i = min(footer_i, i)

        for k, (line_i, sku) in enumerate(sku_rows):
            start_i = line_i
            if k > 0:
                prev_sku_line = sku_rows[k-1][0]
                start_i = max(prev_sku_line + 1, line_i - 2)
                
            end_i = min(footer_i - 1, line_i + 2)
            if k < len(sku_rows) - 1:
                next_sku_line = sku_rows[k+1][0]
                end_i = next_sku_line - 1
                
            candidate_lines = []
            for idx_l in range(start_i, end_i + 1):
                if (idx_l not in used_line_indices or idx_l == line_i) and idx_l < footer_i:
                    candidate_lines.append((idx_l, lines[idx_l]))

            best_math = None
            best_score = -1
            best_cl_idx = None
            best_desc_extra = ''

            for cl_idx, cl_txt in candidate_lines:
                clean_cl = clean_line_for_dim_nums(cl_txt)
                tokens = clean_cl.split()
                nums = [parse_float_digits(t) for t in tokens if parse_float_digits(t) > 0]
                
                curr_line_clean = clean_line_for_dim_nums(lines[line_i])
                curr_nums = [parse_float_digits(t) for t in curr_line_clean.split() if parse_float_digits(t) > 0]

                all_nums = list(set(nums + curr_nums))
                cand_q_list = list(set([1] + [n for n in all_nums if 1 <= n <= 1000]))
                cand_tot_list = list(all_nums)

                for q in cand_q_list:
                    for p in all_nums:
                        if p >= 10 and (q * p) <= 100000000:
                            cand_tot_list.append(q * p)
                            
                for p in all_nums:
                    if p >= 10:
                        for tot in all_nums:
                            if tot > p:
                                calc_q = round(tot / p)
                                if 1 <= calc_q <= 1000 and abs((calc_q * p) - tot) < 5:
                                    cand_q_list.append(calc_q)

                for q in cand_q_list:
                    if 1 <= q <= 1000:
                        for p in all_nums:
                            for tot in cand_tot_list:
                                if q > 1 and p >= tot:
                                    continue
                                
                                diff = abs((q * p) - tot)
                                is_valid_math = False
                                if tot < 1000 and diff == 0:
                                    is_valid_math = True
                                elif tot >= 1000 and (diff < 5 or (tot >= 100000 and (diff / float(tot)) < 0.001)):
                                    is_valid_math = True

                                if is_valid_math and tot >= p and (q != tot or q == 1):
                                    if p < 10 and q <= 2 and tot < 10:
                                        continue
                                    
                                    dist_penalty = abs(cl_idx - line_i) * 1000
                                    score = tot - dist_penalty
                                    
                                    if p in curr_nums and tot in curr_nums:
                                        if q in curr_nums and q > 1:
                                            score += 500000000000
                                        score += 100000000000
                                    elif cl_idx == line_i:
                                        score += 50000000000
                                    elif tot in all_nums:
                                        score += 10000000000
                                    elif (q in curr_nums and p in curr_nums):
                                        score += 1000000000
                                        
                                    if cl_idx <= line_i:
                                        score += 500000000
                                    if q > 1 and p < tot:
                                        score += 500000000
                                    if diff == 0:
                                        score += 50000000
                                    if score > best_score:
                                        best_score = score
                                        best_math = (q, p, tot)
                                        best_cl_idx = cl_idx
                                        best_desc_extra = cl_txt

            if not best_math:
                continue
                
            q_val, p_val, tot_val = best_math

            if best_cl_idx is not None:
                used_line_indices.add(best_cl_idx)
            used_line_indices.add(line_i)

            combined_desc_text = f"{lines[line_i]} {best_desc_extra}" if best_cl_idx != line_i else lines[line_i]
            unit = 'PCS'
            m_unit = re.search(r'\b(ROLL|PCS|UNIT|BOX|SET|KG|PACK|LOT)\b', combined_desc_text, re.IGNORECASE)
            if m_unit:
                unit = m_unit.group(1).upper()

            desc = combined_desc_text
            for s_item in all_skus:
                desc = desc.replace(s_item, '')
            desc = re.sub(r'^\d+[\.\s]+', '', desc.strip())
            desc_tokens = desc.split()
            clean_words = []
            for i_w, w in enumerate(desc_tokens):
                w_flt = parse_float_digits(w)
                next_w = desc_tokens[i_w + 1].lower() if i_w + 1 < len(desc_tokens) else ""
                prev_w = desc_tokens[i_w - 1].lower() if i_w > 0 else ""
                is_dimension = next_w in ["inch", "in", "mm", "cm", "m"] or re.match(r'^M\d+$', w, re.IGNORECASE) or prev_w in ['×', 'x', '*'] or w in ['×', 'x', '*']
                if not is_dimension and (w.upper() == unit or w_flt in [q_val, p_val, tot_val] or abs(w_flt - tot_val) < 1000 or abs(w_flt - p_val) < 0.5):
                    continue
                clean_words.append(w)
            desc_clean = ' '.join(clean_words).strip()
            desc_clean = re.sub(r'^\d{3,}\s*', '', desc_clean)

            parsed_items.append({
                'no': str(k + 1),
                'sku': sku,
                'description': desc_clean,
                'qty': str(int(q_val)),
                'unit': unit,
                'unit_price': fmt_num(p_val),
                'total': fmt_num(tot_val)
            })

        if parsed_items:
            vendor_data["items"] = parsed_items
            vendor_data["quantity"] = str(len(parsed_items))
            vendor_data["item_name"] = ", ".join([it["description"] for it in parsed_items if it.get("description")])
            vendor_data["unit_price"] = ", ".join([str(it.get("unit_price", "0")) for it in parsed_items if it.get("unit_price")])

        # Sanitize & apply global math verification engine
        from .invoice_parser import clean_final_invoice_data
        vendor_data = clean_final_invoice_data(vendor_data, raw_prompt=prompt)

        for k, v in vendor_data.items():
            if isinstance(v, str):
                vendor_data[k] = self.sanitize_str(v)

        return vendor_data
