import os
import sys
import json
import tempfile
import streamlit as st
from PIL import Image

# Ensure backend directory is in Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app import ocr_engine
from app.pii_masker import PIIMasker
from app.parsers.ktp_parser import KTPParser
from app.parsers.passport_parser import PassportParser
from app.parsers.invoice_parser import InvoiceParser
from app.parsers.vendor_doc_parser import VendorDocumentParser
from app.parsers.business_card_parser import BusinessCardParser
from app.parsers.general_doc_parser import GeneralDocumentParser
from app.verification import verify_and_reconcile_invoice_math

# Page Config
st.set_page_config(
    page_title="Smart Document Organizer IDP",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.6rem 1rem;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #1d4ed8 0%, #6d28d9 100%);
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📑 Smart Document Organizer IDP</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Intelligent Document Processing & Data Extraction</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Document Settings")
    
    doc_type = st.selectbox(
        "Document Type Target",
        ["Auto-Detect", "KTP / Identity Card", "Passport", "Invoice / Struk", "Vendor / Supply Chain", "Business Card", "General Document"]
    )
    
    enable_masking = st.checkbox("🔒 Enable PII Data Masking", value=True)
    
    st.divider()
    st.subheader("📤 Upload Document")
    uploaded_file = st.file_uploader(
        "Choose an image (PNG, JPG) or PDF file",
        type=["png", "jpg", "jpeg", "pdf"]
    )

# Main Processing Layout
if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🖼️ Document Preview")
        file_bytes = uploaded_file.read()
        
        # Save temp file
        ext = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            if ext.lower() == ".pdf":
                st.info("📄 PDF Document Loaded")
            else:
                image = Image.open(io.BytesIO(file_bytes) if 'io' in locals() else tmp_path)
                st.image(image, use_container_width=True)
        except Exception:
            st.warning("Preview not available for this file type.")

    with col2:
        st.subheader("⚡ Data Extraction")
        
        if st.button("🚀 Process & Extract Document"):
            with st.spinner("Extracting text with High-Precision PaddleOCR..."):
                try:
                    # 1. OCR Scan
                    ocr_res = ocr_engine.extract_text_from_file(tmp_path)
                    raw_text = ocr_res.get("text", "")
                    
                    # 2. PII Masking
                    masker = PIIMasker()
                    masked_text, pii_map = masker.mask_text(raw_text) if enable_masking else (raw_text, {})
                    
                    # 3. Document Parsing
                    prompt_txt = masked_text if enable_masking else raw_text
                    
                    # Auto-detect target
                    target = doc_type
                    if target == "Auto-Detect":
                        if any(kw in raw_text.upper() for kw in ["PROVINSI", "NIK", "GOL. DARAH"]):
                            target = "KTP / Identity Card"
                        elif "PASSPORT" in raw_text.upper() or "PASPOR" in raw_text.upper():
                            target = "Passport"
                        elif any(kw in raw_text.upper() for kw in ["VENDOR", "PO NO", "PURCHASE ORDER"]):
                            target = "Vendor / Supply Chain"
                        else:
                            target = "Invoice / Struk"
                            
                    if target == "KTP / Identity Card":
                        parsed = KTPParser().parse(prompt_txt)
                    elif target == "Passport":
                        parsed = PassportParser().parse(prompt_txt)
                    elif target == "Vendor / Supply Chain":
                        parsed = VendorDocumentParser().parse(prompt_txt)
                        parsed = verify_and_reconcile_invoice_math(parsed)
                    elif target == "Invoice / Struk":
                        parsed = InvoiceParser().parse(prompt_txt)
                        parsed = verify_and_reconcile_invoice_math(parsed)
                    elif target == "Business Card":
                        parsed = BusinessCardParser().parse(prompt_txt)
                    else:
                        parsed = GeneralDocumentParser().parse(prompt_txt)
                        
                    # 4. Unmask if needed
                    if enable_masking and pii_map:
                        parsed = masker.unmask_json(parsed, pii_map)
                        
                    st.success(f"✅ Extraction Complete ({target})!")
                    st.json(parsed)
                    
                except Exception as e:
                    st.error(f"Error during extraction: {str(e)}")
                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
else:
    st.info("👆 Please upload a document file (Image or PDF) from the sidebar to begin processing.")
