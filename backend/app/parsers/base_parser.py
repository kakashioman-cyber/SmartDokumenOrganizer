import re

class BaseDocumentParser:
    """Base class for all modular document parsers."""
    
    def parse(self, prompt: str) -> dict:
        raise NotImplementedError("Subclasses must implement parse()")

    @staticmethod
    def sanitize_str(val) -> str:
        """Strip newlines, carriage returns, and excess whitespace."""
        if isinstance(val, str):
            v = val.replace('\n', ' ').replace('\r', '').strip()
            v = re.sub(r'\s+', ' ', v).strip()
            return v
        return "N/A"

    @staticmethod
    def clean_prefix(text: str, prefixes: list) -> str:
        """Remove label prefixes from extracted value strings."""
        if not text or text == "N/A":
            return "N/A"
        res = text.strip()
        for p in prefixes:
            res = re.sub(rf'^[/\s]*{re.escape(p)}[:.;,\s-]*', '', res, flags=re.IGNORECASE).strip()
        res = re.sub(r'^[:;.,\s-]+', '', res).strip()
        return res if res else "N/A"
