import os
import json
import logging
import re
import io
from typing import Dict, Any, Tuple

from . import parsers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMConnector")

def detect_document_type(prompt: str) -> str:
    """
    High-accuracy weighted AI classifier: analyzes raw OCR text and automatically detects
    the document category (ktp | passport | invoice | vendor | business_card | general).
    """
    text_upper = prompt.upper()
    lines = [l.strip() for l in prompt.split('\n') if l.strip()]

    scores = {
        "ktp": 0,
        "passport": 0,
        "invoice": 0,
        "vendor": 0,
        "business_card": 0,
        "general": 0
    }

    # 1. Passport Indicators
    if any('<' in line or line.startswith('P<') for line in lines):
        scores["passport"] += 10
    for kw in ["PASSPORT", "PASPOR", "REPUBLIK INDONESIA", "ISSUING OFFICE", "NATIONALITY", "COUNTRY CODE", "SURNAME", "GIVEN NAMES"]:
        if kw in text_upper:
            scores["passport"] += 4

    # 2. KTP Indicators
    if re.search(r'\b\d{16}\b', prompt) or "[NIK_" in prompt:
        scores["ktp"] += 6
    for kw in ["NIK", "PROVINSI", "KOTA", "KARTU TANDA PENDUDUK", "PENDUDUK", "BERLAKU HINGGA", "SEUMUR HIDUP", "RT/RW", "KEL/DESA", "KECAMATAN", "AGAMA", "STATUS PERKAWINAN", "PERKAWINAN", "PEKERJAAN", "TEMPAT/TGL LAHIR", "TEMPAT TGL LAHIR", "TEMPAL", "GOL. DARAH", "WNI", "BELUM KAWIN", "PELAJAR"]:
        if kw in text_upper:
            scores["ktp"] += 3

    # B2B Corporate Entity Detection (PT/CV Vendor + PT/CV Customer)
    org_matches = re.findall(r'\b(?:PT|CV|UD|Tbk|Ltd|Corp|Inc)\b', prompt, re.IGNORECASE)
    if len(org_matches) >= 2:
        scores["vendor"] += 10
    elif len(org_matches) == 1:
        scores["vendor"] += 4

    # Retail / Kasir / Struk Detection (Exclusive to actual retail receipt keywords, not company titles like 'Supermarket')
    if any(kw in text_upper for kw in ["KASIR", "TUNAI", "KEMBALI", "ITEMS SOLD", "POS", "RECEIPT NO", "STRUK PEMBAYARAN"]):
        scores["invoice"] += 12

    # 3. Vendor / Procurement PO Indicators (Presence of PO / Supplier / DO = Heavy Vendor Signal)
    has_po_or_do = any(kw in text_upper for kw in [
        "PURCHASE ORDER", "NOMOR PO", "NO. PO", "PO NO", "PO #", "PO-", "PO DATE", "PO EXPIRY",
        "SUPPLIER NAME", "SUPPLIER CODE", "SUPPLIER", "SURAT JALAN", "DELIVERY ORDER", "BERITA ACARA",
        "SUPPLY CHAIN", "TABEL BARANG", "PENGADAAN", "HSN CODE", "VNDR-"
    ]) or bool(re.search(r'\b(?:NO\.?\s*)?PO\s*[-#:]?\s*\d{2,10}\b', text_upper))
    
    if has_po_or_do:
        scores["vendor"] += 15

    for kw in ["NO KONTRAK", "PENYEDIA", "SUPPLIER", "PENGADAAN", "DEPARTEMEN", "SPK", "SURAT PESANAN", "DOKUMEN VENDOR", "MATERIAL", "SPESIFIKASI", "LOGISTIK"]:
        if kw in text_upper:
            scores["vendor"] += 4

    # 4. Invoice / Struk Indicators
    if any(kw in text_upper for kw in ["INVOICE #", "NO INVOICE", "NOMOR INVOICE", "FAKTUR", "KWITANSI", "STRUK PEMBAYARAN", "BILLING STATEMENT"]):
        scores["invoice"] += 6
    for kw in ["INVOICE", "STRUK", "NOTA", "FAKTUR", "RECEIPT", "TOTAL BILL", "TOTAL PEMBAYARAN", "GRAND TOTAL", "SUBTOTAL", "DUE DATE", "REKENING"]:
        if kw in text_upper:
            scores["invoice"] += 3

    # 5. Business Card Indicators
    has_email = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', prompt))
    has_phone = bool(re.search(r'\+?\b\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}\b', prompt))
    if len(prompt) < 600 and has_email and has_phone:
        scores["business_card"] += 5

    # 6. General / Tax / NPWP Indicators
    for kw in ["NPWP", "NIB", "SERTIFIKAT", "CERTIFICATE", "SURAT IZIN", "TAX ID", "IZIN USOHA"]:
        if kw in text_upper:
            scores["general"] += 3

    # Pick top scoring category
    best_category = max(scores, key=scores.get)
    if scores[best_category] > 0:
        logger.info(f"AI Classifier scores: {scores} -> Selected: {best_category}")
        return best_category

    # Default fallback
    return "general"

def analyze_document_text(prompt: str, doc_type: str = "auto") -> Tuple[Dict[str, Any], str]:
    try:
        effective_type = doc_type.lower().strip()
        if effective_type in ["auto", "", "none"]:
            effective_type = detect_document_type(prompt)
            logger.info(f"AI Auto-Detected Document Category: {effective_type}")

        parser = parsers.get_parser(effective_type)
        import inspect
        sig = inspect.signature(parser.parse)
        if 'forced_type' in sig.parameters:
            res_data = parser.parse(prompt, forced_type=effective_type)
        else:
            res_data = parser.parse(prompt)
            
        return res_data, effective_type
    except Exception as e:
        logger.error(f"Error analyzing document text: {e}")
        return {"error": str(e), "raw_prompt": prompt}, doc_type

def clean_api_key(k: str) -> str:
    if not k:
        return ""
    return str(k).strip().strip('"').strip("'").replace('\n', '').replace('\r', '').replace(' ', '')

def sanitize_category_fields(data: dict, effective_type: str) -> dict:
    cat = effective_type.lower().strip()
    if cat == "ktp":
        from app.parsers.ktp_parser import format_ktp_name, format_ktp_address
        nik_val = str(data.get("id_number") or data.get("nik") or data.get("invoice_number") or "").strip()
        pob = data.get("place_of_birth") or data.get("tempat_lahir", "N/A")
        dob = data.get("date_of_birth") or data.get("tanggal_lahir", "N/A")
        raw_name = str(data.get("full_name") or data.get("nama") or data.get("customer_name") or "N/A").strip()
        raw_addr = str(data.get("address") or data.get("alamat", "N/A")).strip()
        return {
            "id_number": nik_val if (nik_val and len(nik_val) >= 12 and nik_val != "N/A") else str(data.get("id_number", "N/A")),
            "full_name": format_ktp_name(raw_name),
            "place_of_birth": str(pob).strip(),
            "date_of_birth": str(dob).strip(),
            "gender": str(data.get("gender") or data.get("jenis_kelamin", "N/A")).strip(),
            "blood_type": str(data.get("blood_type") or data.get("gol_darah", "N/A")).strip(),
            "address": format_ktp_address(raw_addr),
            "rt_rw": str(data.get("rt_rw", "N/A")).strip(),
            "kel_desa": str(data.get("kel_desa", "N/A")).strip(),
            "kecamatan": str(data.get("kecamatan", "N/A")).strip(),
            "religion": str(data.get("religion") or data.get("agama", "N/A")).strip(),
            "marital_status": str(data.get("marital_status") or data.get("status_perkawinan", "N/A")).strip(),
            "occupation": str(data.get("occupation") or data.get("pekerjaan", "N/A")).strip(),
            "nationality": str(data.get("nationality") or data.get("kewarganegaraan", "WNI")).strip(),
            "expiry_date": str(data.get("expiry_date") or data.get("berlaku_hingga", "SEUMUR HIDUP")).strip()
        }
    elif cat == "passport":
        from app.parsers.passport_parser import format_passport_name
        pass_num = str(data.get("passport_number") or data.get("id_number") or "N/A").strip()
        raw_pname = str(data.get("full_name") or data.get("nama") or "N/A").strip()
        return {
            "document_type": "Passport",
            "passport_type": str(data.get("passport_type") or "P").strip(),
            "country_code": str(data.get("country_code") or "IDN").strip(),
            "passport_number": pass_num,
            "full_name": format_passport_name(raw_pname),
            "place_of_birth": str(data.get("place_of_birth") or data.get("tempat_lahir", "N/A")).strip(),
            "date_of_birth": str(data.get("date_of_birth") or data.get("tanggal_lahir", "N/A")).strip(),
            "gender": str(data.get("gender") or data.get("sex", "N/A")).strip(),
            "nationality": str(data.get("nationality") or "INDONESIA").strip(),
            "issue_date": str(data.get("issue_date") or data.get("date_of_issue", "N/A")).strip(),
            "expiry_date": str(data.get("expiry_date") or data.get("date_of_expiry", "N/A")).strip(),
            "registration_no": str(data.get("registration_no") or data.get("no_reg", "N/A")).strip(),
            "issuing_office": str(data.get("issuing_office") or data.get("issuing_authority", "N/A")).strip(),
            "mrz_code": str(data.get("mrz_code") or data.get("mrz_line1", "N/A")).strip()
        }
    elif cat == "business_card":
        return {
            "contact_name": str(data.get("contact_name") or data.get("full_name") or "N/A").strip(),
            "job_title": str(data.get("job_title", "N/A")).strip(),
            "company_name": str(data.get("company_name") or data.get("vendor_name", "N/A")).strip(),
            "phone_number": str(data.get("phone_number", "N/A")).strip(),
            "email_address": str(data.get("email_address", "N/A")).strip(),
            "website_url": str(data.get("website_url", "N/A")).strip()
        }
    elif cat == "invoice":
        return {
            "vendor_name": str(data.get("vendor_name", "N/A")).strip(),
            "customer_name": str(data.get("customer_name", "N/A")).strip(),
            "invoice_number": str(data.get("invoice_number", "N/A")).strip(),
            "invoice_date": str(data.get("invoice_date", "N/A")).strip(),
            "due_date": str(data.get("due_date", "N/A")).strip(),
            "subtotal": str(data.get("subtotal", "0.00")).strip(),
            "tax": str(data.get("tax", "0.00")).strip(),
            "total_amount": str(data.get("total_amount", "N/A")).strip(),
            "currency": str(data.get("currency", "IDR")).strip(),
            "items": data.get("items", [])
        }
    elif cat in ["vendor", "vendor_doc", "po"]:
        return {
            "vendor_name": str(data.get("vendor_name", "N/A")).strip(),
            "customer_name": str(data.get("customer_name", "N/A")).strip(),
            "po_number": str(data.get("po_number", "N/A")).strip(),
            "invoice_number": str(data.get("invoice_number", "N/A")).strip(),
            "delivery_order_number": str(data.get("delivery_order_number", "N/A")).strip(),
            "order_date": str(data.get("order_date", "N/A")).strip(),
            "delivery_date": str(data.get("delivery_date", "N/A")).strip(),
            "subtotal": str(data.get("subtotal", "0.00")).strip(),
            "tax": str(data.get("tax", "11%")).strip(),
            "tax_amount": str(data.get("tax_amount", "0.00")).strip(),
            "total_amount": str(data.get("total_amount", "N/A")).strip(),
            "currency": str(data.get("currency", "IDR")).strip(),
            "items": data.get("items", [])
        }
    else:
        return {
            "document_title": str(data.get("document_title") or data.get("title") or "Dokumen Bisnis / Pajak / Sertifikat").strip(),
            "tax_id_npwp": str(data.get("tax_id_npwp") or data.get("npwp", "N/A")).strip(),
            "business_license_nib": str(data.get("business_license_nib") or data.get("nib", "N/A")).strip(),
            "certificate_number": str(data.get("certificate_number") or data.get("no_sertifikat", "N/A")).strip(),
            "issue_date": str(data.get("issue_date", "N/A")).strip(),
            "summary": str(data.get("summary") or "Dokumen terproses secara otomatis.").strip()
        }

def post_process_extracted_data(parsed_data: dict, effective_type: str, raw_text: str = "") -> Tuple[dict, str]:
    if not isinstance(parsed_data, dict):
        return parsed_data, effective_type

    nik = str(parsed_data.get("nik") or parsed_data.get("id_number") or "").strip()
    passport_num = str(parsed_data.get("passport_number") or "").strip()
    inv_num = str(parsed_data.get("invoice_number") or parsed_data.get("invoice_no") or parsed_data.get("inv_no") or parsed_data.get("no_invoice") or parsed_data.get("invoice_num") or parsed_data.get("inv_number") or parsed_data.get("invoice_id") or parsed_data.get("no_faktur") or "").strip()
    if inv_num:
        parsed_data["invoice_number"] = inv_num
    po_num = str(parsed_data.get("po_number") or parsed_data.get("po_no") or parsed_data.get("no_po") or "").strip()
    if po_num:
        parsed_data["po_number"] = po_num
    doc_type_field = str(parsed_data.get("document_type", "") or parsed_data.get("document_category", "")).lower()

    # 1. KTP Check (Priority 1)
    is_ktp = "ktp" in doc_type_field or "id_card" in doc_type_field or (nik and (len(nik) >= 12 or any(k in parsed_data for k in ["rt_rw", "kel_desa", "kecamatan", "gol_darah", "agama", "status_perkawinan"])))
    if is_ktp:
        effective_type = "ktp"
        if raw_text:
            try:
                from app.parsers.ktp_parser import KTPParser
                rule_data = KTPParser().parse(raw_text, raw_text.split('\n'))
                for k, v in rule_data.items():
                    cur = str(parsed_data.get(k, "")).strip()
                    if (not cur or cur.upper() in ["N/A", "NULL", "NONE", "UNDEFINED"]) and v and str(v).upper() not in ["N/A", "NULL", "NONE", "UNDEFINED"]:
                        parsed_data[k] = v
            except Exception:
                pass
        parsed_data["id_number"] = parsed_data.get("id_number") or nik or "N/A"
        parsed_data["full_name"] = parsed_data.get("full_name") or parsed_data.get("nama") or "N/A"
        return sanitize_category_fields(parsed_data, "ktp"), "ktp"

    # 2. Passport Check (Priority 2)
    is_passport = "passport" in doc_type_field or "paspor" in doc_type_field or (passport_num and passport_num.upper() not in ["N/A", "NULL", "NONE", "", "-", "UNDEFINED"])
    if is_passport:
        effective_type = "passport"
        if raw_text:
            try:
                from app.parsers.passport_parser import PassportParser
                rule_data = PassportParser().parse(raw_text, raw_text.split('\n'))
                for k, v in rule_data.items():
                    cur = str(parsed_data.get(k, "")).strip()
                    if (not cur or cur.upper() in ["N/A", "NULL", "NONE", "UNDEFINED"]) and v and str(v).upper() not in ["N/A", "NULL", "NONE", "UNDEFINED"]:
                        parsed_data[k] = v
            except Exception:
                pass
        parsed_data["passport_number"] = parsed_data.get("passport_number") or passport_num or "N/A"
        parsed_data["full_name"] = parsed_data.get("full_name") or parsed_data.get("nama") or "N/A"
        return sanitize_category_fields(parsed_data, "passport"), "passport"

    # 3. Vendor PO Check (Priority 3) & Rule Enhancement Merge
    if raw_text:
        try:
            from app.parsers.vendor_doc_parser import VendorDocumentParser
            rule_vdata = VendorDocumentParser().parse(raw_text)
            
            rule_po = rule_vdata.get("po_number", "N/A")
            if rule_po != "N/A" and (po_num in ["N/A", "NONE", "NULL", "", "-"] or not po_num):
                parsed_data["po_number"] = rule_po
                po_num = rule_po
                
            rule_inv = rule_vdata.get("invoice_number", "N/A")
            if rule_inv != "N/A" and (inv_num in ["N/A", "NONE", "NULL", "", "-"] or not inv_num):
                parsed_data["invoice_number"] = rule_inv
                inv_num = rule_inv
                
            if parsed_data.get("order_date") in ["N/A", None, ""] and rule_vdata.get("order_date") != "N/A":
                parsed_data["order_date"] = rule_vdata.get("order_date")
            if parsed_data.get("invoice_date") in ["N/A", None, ""] and rule_vdata.get("order_date") != "N/A":
                parsed_data["invoice_date"] = rule_vdata.get("order_date")
                
            if parsed_data.get("tax") in ["0%", "0.00", "0", "N/A", None] and rule_vdata.get("tax") != "0%":
                parsed_data["tax"] = rule_vdata.get("tax")
                parsed_data["tax_amount"] = rule_vdata.get("tax_amount")
                
            if "IDR" in raw_text.upper() or "RP" in raw_text.upper() or "TANGGAL" in raw_text.upper() or "PPN" in raw_text.upper():
                parsed_data["currency"] = "IDR"
                
            rule_items = rule_vdata.get("items", [])
            vision_items = parsed_data.get("items", [])
            if isinstance(vision_items, list) and isinstance(rule_items, list):
                for i, v_it in enumerate(vision_items):
                    if isinstance(v_it, dict) and i < len(rule_items):
                        if v_it.get("sku") in ["-", "N/A", None, ""] or not v_it.get("sku"):
                            v_it["sku"] = rule_items[i].get("sku", "-")
        except Exception:
            pass

    if po_num and po_num.upper() not in ["N/A", "NULL", "NONE", "", "-", "UNDEFINED"]:
        effective_type = "vendor"
    elif inv_num and inv_num.upper() not in ["N/A", "NULL", "NONE", "", "-", "UNDEFINED"]:
        effective_type = "invoice"
    elif "vendor" in doc_type_field or "po" in doc_type_field or "purchase" in doc_type_field:
        effective_type = "vendor"
    elif "invoice" in doc_type_field:
        effective_type = "invoice"

    # Normalize invoice_number if OCR read INVIAN -> INV/AN
    if inv_num:
        inv_num_clean = re.sub(r'\bINVIAN-', 'INV/AN-', inv_num, flags=re.IGNORECASE)
        inv_num_clean = re.sub(r'\bINV AN-', 'INV/AN-', inv_num_clean, flags=re.IGNORECASE)
        parsed_data["invoice_number"] = inv_num_clean

    # 4. Normalize Item Table & Check Top-to-Bottom Order
    if "items" in parsed_data and isinstance(parsed_data["items"], list) and len(parsed_data["items"]) > 0:
        items_list = parsed_data["items"]
        if len(items_list) > 1 and raw_text:
            first_desc = str(items_list[0].get("description", "")).strip()
            last_desc = str(items_list[-1].get("description", "")).strip()
            pos_first = raw_text.find(first_desc) if first_desc else -1
            pos_last = raw_text.find(last_desc) if last_desc else -1
            if pos_first != -1 and pos_last != -1 and pos_first > pos_last:
                logger.info("Detected reversed item extraction in LLM output! Reversing items array to top-to-bottom order...")
                items_list.reverse()

        for idx, item in enumerate(items_list):
            if isinstance(item, dict):
                item["no"] = str(idx + 1)
                
                sku_val = str(item.get("sku") or item.get("part_no") or item.get("part_number") or item.get("code") or item.get("item_code") or "").strip()
                if not sku_val or sku_val in ["-", "N/A", "null", "None"]:
                    desc = str(item.get("description", ""))
                    m_sku = re.search(r'\b([A-Za-z0-9]{3,6}-[A-Za-z0-9]{3,6}(?:-\d{3,4})?|\d{4,6})\b', desc)
                    if m_sku and m_sku.group(1).upper() not in ["INCH", "BOX", "UNIT", "PCS", "PACK", "ROLL", "EACH"]:
                        sku_val = m_sku.group(1)
                item["sku"] = sku_val if sku_val else "-"

                raw_qty = str(item.get("qty", "1")).strip()
                m_unit = re.search(r'\b(kg|Kg|KG|pack|pcs|Pcs|PCS|lembar|uom|UOM|box|Box|BOX|unit|Unit|UNIT|roll|Roll|ROLL|each|Each|EACH|set|Set|SET)\b', raw_qty)
                if m_unit:
                    item["unit"] = m_unit.group(1)
                    item["qty"] = re.sub(r'[^\d.]', '', raw_qty).strip() or "1"
                
                curr_unit = str(item.get("unit", "")).strip()
                if not curr_unit or curr_unit in ["N/A", "null", "None", ""]:
                    item["unit"] = "pcs"

    # Harmonize currency & amount strings
    from app.parsers.invoice_parser import clean_final_invoice_data
    parsed_data = clean_final_invoice_data(parsed_data, raw_text)

    # 5. Business Card Check
    is_biz_card = "business_card" in doc_type_field or "kartu_nama" in doc_type_field or any(k in parsed_data for k in ["job_title", "company_name", "phone_number", "email_address", "website_url"])
    if is_biz_card and not inv_num and not po_num and not nik and not passport_num:
        return sanitize_category_fields(parsed_data, "business_card"), "business_card"

    # 6. Fallback General Business / Tax / Certificate Document Check
    if effective_type not in ["ktp", "passport", "vendor", "invoice", "business_card"]:
        effective_type = "general"

    return sanitize_category_fields(parsed_data, effective_type), effective_type

def analyze_document_image(image_bytes: bytes, doc_type: str = "auto", provider: str = "auto", custom_api_key: str = "", raw_text: str = "") -> Tuple[Dict[str, Any], str]:
    """
    Direct Vision AI Engine (Option B): Processes raw image Base64 directly using
    Vision Models (Google Gemini 1.5 / OpenAI GPT-4o / Anthropic Claude 3.5 Sonnet),
    bypassing OCR text degradation on complex/damaged scans.
    """
    import base64
    import urllib.request
    import urllib.parse
    import urllib.error
    try:
        effective_type = doc_type.lower().strip()
        
        # Robust Image & PDF Preprocessing Pipeline
        try:
            import io, base64, pypdfium2
            from PIL import Image, ImageOps, ImageEnhance
            
            raw_data = image_bytes
            if isinstance(raw_data, str):
                if raw_data.startswith('data:'):
                    raw_data = base64.b64decode(raw_data.split(',', 1)[1])
                else:
                    raw_data = base64.b64decode(raw_data)
            elif isinstance(raw_data, bytes):
                if raw_data.startswith(b'data:'):
                    str_data = raw_data.decode('utf-8', errors='ignore')
                    if ',' in str_data:
                        raw_data = base64.b64decode(str_data.split(',', 1)[1])

            if isinstance(raw_data, bytes) and raw_data.startswith(b'%PDF'):
                pdf = pypdfium2.PdfDocument(raw_data)
                img = pdf[0].render(scale=2.0).to_pil()
            elif isinstance(raw_data, Image.Image):
                img = raw_data
            else:
                img = Image.open(io.BytesIO(raw_data))
                
            img = ImageOps.exif_transpose(img)
            img = img.convert('RGB')
            
            # Contrast & Brightness Enhancement for dim/dark scans
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.25)

            # Fast CPU Vision Optimization: Scale down high-resolution scans to max 1024px
            if max(img.size) > 1024:
                img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=95)
            clean_image_bytes = buf.getvalue()
            base64_img = base64.b64encode(clean_image_bytes).decode('utf-8')
        except Exception as img_err:
            logger.warning(f"Image preprocessing fallback: {img_err}")
            clean_bytes = image_bytes if isinstance(image_bytes, bytes) else b""
            base64_img = base64.b64encode(clean_bytes).decode('utf-8') if clean_bytes else ""
        
        c_key = clean_api_key(custom_api_key)
        
        if c_key:
            if provider in ["openai", "gpt4o"]:
                openai_key = c_key
                gemini_key = clean_api_key(os.getenv("GEMINI_API_KEY", ""))
                anthropic_key = clean_api_key(os.getenv("ANTHROPIC_API_KEY", ""))
                logger.info("🔑 Using Custom OpenAI API Key provided from UI input.")
            elif provider in ["claude", "anthropic"]:
                anthropic_key = c_key
                gemini_key = clean_api_key(os.getenv("GEMINI_API_KEY", ""))
                openai_key = clean_api_key(os.getenv("OPENAI_API_KEY", ""))
                logger.info("🔑 Using Custom Anthropic API Key provided from UI input.")
            else:
                gemini_key = c_key
                openai_key = clean_api_key(os.getenv("OPENAI_API_KEY", ""))
                anthropic_key = clean_api_key(os.getenv("ANTHROPIC_API_KEY", ""))
                logger.info("🔑 Using Custom Google Gemini API Key provided from UI input.")
        else:
            gemini_key = clean_api_key(os.getenv("GEMINI_API_KEY", ""))
            openai_key = clean_api_key(os.getenv("OPENAI_API_KEY", ""))
            anthropic_key = clean_api_key(os.getenv("ANTHROPIC_API_KEY", ""))
            logger.info("🔑 Using Default API Keys from .env environment file.")

        # 1. Google Gemini Vision API (Primary Cloud AI Vision Engine)
        if provider in ["gemini", "google", "cloud_vision", "auto"]:
            if not gemini_key or "isi_dengan" in gemini_key:
                # If Gemini key isn't provided, fall back to Local Rule Preprocessing Engine
                from . import ocr_engine
                logger.info("No Gemini API key provided. Falling back to Local Rule Preprocessing Engine...")
                ocr_res = ocr_engine.process_document(image_bytes, "direct_vision_doc.jpg")
                raw_text = ocr_res.get("text", "")
                if effective_type in ["auto", "", "none"]:
                    effective_type = detect_document_type(raw_text)
                parser = parsers.get_parser(effective_type)
                res_data = parser.parse(raw_text)
                return res_data, effective_type

            logger.info("Calling Direct Google Gemini Vision API...")
            encoded_g_key = urllib.parse.quote(gemini_key)
            models_to_try = ["gemini-flash-latest", "gemini-2.0-flash-exp", "gemini-1.5-flash-latest"]
            
            prompt_text = f"""Extract structured JSON for document category: '{effective_type}'.
Return ONLY valid JSON with fields: vendor_name, customer_name, id_number, full_name, place_of_birth, date_of_birth, gender, blood_type, address, rt_rw, kel_desa, kecamatan, religion, marital_status, occupation, nationality, issue_date, expiry_date, issuing_office, invoice_number, po_number, invoice_date, order_date, due_date, delivery_date, subtotal, tax, tax_amount, total_amount, currency, items (array of {{no, sku, description, qty, unit, unit_price, total}}).
CRITICAL EXTRACTION RULES:
1. Currency: Detect the EXACT currency printed on the document (e.g., SGD, USD, EUR, IDR, INR). If SGD or S$ is present, set currency to "SGD". If USD or $ is present, set currency to "USD". Output "IDR" ONLY if Rp or IDR is printed.
2. PO Number: Extract PO number from "No. PO", "PO #", "PO-...", "Purchase Order".
3. Dates: Extract specific dates if printed separately (invoice_date, order_date, due_date, delivery_date, issue_date, date_of_birth). If only a single generic "Tanggal" or "Date" is printed, assign it to invoice_date and order_date.
4. Part No / SKU: Extract "Part No", "Part Number", "Kode Barang", "SKU" into the "sku" field for each item (e.g. AN-BRG-895).
5. Tax: Extract ANY tax rate printed on document (e.g., 12%, 11%, 10%, 9%, 8%, 7%, 5%, 0%, PPN, GST, VAT) into "tax" and the tax amount into "tax_amount".
6. Item Description: Keep ONLY the primary product/item title line. Exclude secondary sub-text, specs, comments, notes, or multi-line remarks.
7. Return strictly valid JSON object without markdown formatting."""

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64_img}}
                    ]
                }]
            }
            req_data = json.dumps(payload).encode('utf-8')
            
            last_error_msg = ""
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={encoded_g_key}"
                try:
                    req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        res_json = json.loads(resp.read().decode('utf-8'))
                        text_resp = res_json['candidates'][0]['content']['parts'][0]['text']
                        clean_json = re.sub(r'^```json\s*|\s*```$', '', text_resp.strip())
                        parsed_vision = json.loads(clean_json)
                        logger.info(f"Direct Gemini Vision extraction success via {model_name}!")
                        return post_process_extracted_data(parsed_vision, effective_type, raw_text="")
                except urllib.error.HTTPError as http_err:
                    err_msg = http_err.read().decode('utf-8')
                    logger.warning(f"Gemini API Model ({model_name}) HTTP {http_err.code}: {err_msg}")
                    last_error_msg = f"HTTP {http_err.code}"
                    if http_err.code == 404:
                        continue
                    elif http_err.code == 429:
                        continue
                except Exception as ex:
                    logger.error(f"Gemini API Exception: {ex}")
                    continue

            if "503" in last_error_msg:
                return {"error": "⚠️ Server Google AI sedang mengalami beban tinggi / sibuk sementara (HTTP 503). Silakan coba lagi beberapa saat lagi."}, effective_type
            elif "429" in last_error_msg:
                return {"error": "⚠️ Batas kecepatan request tercapai (HTTP 429 Rate Limit) atau API Key Gemini tidak valid/kehabisan kuota."}, effective_type
            elif "400" in last_error_msg or "403" in last_error_msg:
                return {"error": f"❌ Google Gemini API Key Ditolak ({last_error_msg}): Kunci API Gemini tidak valid atau tidak memiliki akses."}, effective_type
            else:
                return {"error": f"❌ Google Gemini API Error ({last_error_msg}): Server mengalami gangguan atau API key ditolak."}, effective_type

        # 2. OpenAI GPT-4o API
        elif provider in ["openai", "gpt", "gpt-4o"]:
            if not openai_key or "isi_dengan" in openai_key:
                return {"error": "❌ Kunci OPENAI_API_KEY belum valid. Silakan masukkan OpenAI API Key resmi."}, effective_type
            
            logger.info("Calling OpenAI GPT-4o Vision API...")
            try:
                url = "https://api.openai.com/v1/chat/completions"
                prompt_text = f"Extract structured JSON for document type: '{effective_type}'. Return ONLY valid JSON."
                payload = {
                    "model": "gpt-4o",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                        ]
                    }],
                    "response_format": {"type": "json_object"}
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {openai_key}'})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    res = json.loads(resp.read().decode('utf-8'))
                    text = res['choices'][0]['message']['content']
                    return post_process_extracted_data(json.loads(text), effective_type, raw_text="")
            except urllib.error.HTTPError as http_err:
                err_msg = http_err.read().decode('utf-8')
                logger.error(f"OpenAI API Error: {http_err.code} - {err_msg}")
                return {"error": f"❌ OpenAI API Rejected Key (HTTP {http_err.code}): Kunci API OpenAI ditolak oleh OpenAI Server."}, effective_type

        # 3. Anthropic Claude 3.5 Sonnet API
        elif provider in ["claude", "anthropic"]:
            if not anthropic_key or "isi_dengan" in anthropic_key:
                return {"error": "❌ Kunci ANTHROPIC_API_KEY belum valid. Silakan masukkan Anthropic API Key resmi."}, effective_type

            logger.info("Calling Anthropic Claude 3.5 Sonnet Vision API...")
            try:
                url = "https://api.anthropic.com/v1/messages"
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64_img}},
                            {"type": "text", "text": f"Extract structured JSON for '{effective_type}'. Output valid JSON only."}
                        ]
                    }]
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'x-api-key': anthropic_key, 'anthropic-version': '2023-06-01'})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    res = json.loads(resp.read().decode('utf-8'))
                    text = res['content'][0]['text']
                    clean_json = re.sub(r'^```json\s*|\s*```$', '', text.strip())
                    return post_process_extracted_data(json.loads(clean_json), effective_type, raw_text="")
            except urllib.error.HTTPError as http_err:
                err_msg = http_err.read().decode('utf-8')
                logger.error(f"Claude API Error: {http_err.code} - {err_msg}")
                return {"error": f"❌ Anthropic Claude API Rejected Key (HTTP {http_err.code}): Kunci API Claude ditolak oleh Anthropic Server."}, effective_type

        # 4. Enhanced High-Res Image Preprocessing Fallback (OpenCV CLAHE)
        from . import ocr_engine
        logger.info("Running Advanced Image Sharpening Preprocessing Fallback...")
        ocr_res = ocr_engine.process_document(image_bytes, "direct_vision_doc.jpg")
        raw_text = ocr_res.get("text", "")
        
        if effective_type in ["auto", "", "none"]:
            effective_type = detect_document_type(raw_text)

        parser = parsers.get_parser(effective_type)
        res_data = parser.parse(raw_text)
        return res_data, effective_type
    except Exception as e:
        logger.error(f"Error analyzing document image: {e}")
        return {"error": str(e)}, doc_type

def call_mock_llm(prompt: str, doc_type: str) -> Dict[str, Any]:
    res, _ = analyze_document_text(prompt, doc_type)
    return res
