from .id_card_parser import IDCardParser
from .invoice_parser import InvoiceParser
from .business_card_parser import BusinessCardParser
from .vendor_doc_parser import VendorDocumentParser
from .general_doc_parser import GeneralDocumentParser

id_parser = IDCardParser()

PARSER_REGISTRY = {
    "ktp": id_parser,
    "id_card": id_parser,
    "passport": id_parser,
    "invoice": InvoiceParser(),
    "business_card": BusinessCardParser(),
    "vendor": VendorDocumentParser(),
    "general": GeneralDocumentParser()
}

def get_parser(doc_type: str):
    """Retrieve the dedicated parser instance for a document type."""
    key = str(doc_type).lower().strip()
    if key == "vendor":
        return VendorDocumentParser()
    elif key == "invoice":
        return InvoiceParser()
    elif key in ["ktp", "id_card", "passport"]:
        return IDCardParser()
    elif key == "business_card":
        return BusinessCardParser()
    return GeneralDocumentParser()
