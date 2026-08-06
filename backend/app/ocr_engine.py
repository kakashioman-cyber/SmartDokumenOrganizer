import os
import io
import logging
from PIL import Image
import numpy as np
import cv2
import easyocr
import pypdfium2 as pdfium

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr_engine")

_reader_cache = {}
_paddle_cache = None

def get_ocr_reader(languages=None):
    if languages is None:
        languages = ['en', 'id']
    cache_key = tuple(sorted(languages))
    if cache_key not in _reader_cache:
        logger.info(f"Initializing EasyOCR Reader for languages: {languages}")
        _reader_cache[cache_key] = easyocr.Reader(languages, gpu=True)
    return _reader_cache[cache_key]

def get_paddle_ocr():
    global _paddle_cache
    if _paddle_cache is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("Initializing Optimized High-Speed PaddleOCR Engine...")
            try:
                _paddle_cache = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, text_det_limit_side_len=2000, text_det_limit_type='max', lang='en', enable_mkldnn=False)
            except Exception:
                _paddle_cache = PaddleOCR(lang='en', enable_mkldnn=False)
        except Exception as e:
            logger.warning(f"PaddleOCR primary engine not available: {e}")
            _paddle_cache = False
    return _paddle_cache if _paddle_cache else None

def deskew_document_image(np_img):
    """
    Detects page skew angle using Hough Transform on horizontal text lines and corrects it.
    """
    try:
        if len(np_img.shape) == 3:
            if np_img.shape[2] == 4:
                np_img = cv2.cvtColor(np_img, cv2.COLOR_RGBA2RGB)
            gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = np_img

        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        # Isolate horizontal text lines and eliminate vertical frame lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        text_lines_mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        lines_p = cv2.HoughLinesP(text_lines_mask, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
        angles = []
        if lines_p is not None:
            for line in lines_p:
                x1, y1, x2, y2 = line[0]
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if abs(angle) <= 5.0:
                    angles.append(angle)

        if not angles or abs(float(np.median(angles))) < 0.8 or abs(float(np.median(angles))) > 5.0:
            return np_img

        angle = float(np.median(angles))
        (h, w) = np_img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(np_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        logger.info(f"Auto-Deskew applied: rotated image by {angle:.2f} degrees.")
        return rotated
    except Exception as e:
        logger.warning(f"Deskew preprocessing skipped: {e}")
        return np_img

def enhance_document_image(np_img):
    """
    Applies Auto-Deskewing (pelurusan gambar miring) followed by CLAHE contrast enhancement.
    """
    np_img = deskew_document_image(np_img)
    try:
        if len(np_img.shape) == 3:
            if np_img.shape[2] == 4:
                np_img = cv2.cvtColor(np_img, cv2.COLOR_RGBA2RGB)
            gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        else:
            gray = np_img

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray)
        return cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2RGB)
    except Exception as e:
        logger.warning(f"CLAHE preprocessing skipped: {e}")
        return np_img

def run_paddle_ocr_fallback(np_img):
    p_engine = get_paddle_ocr()
    if not p_engine:
        return ""
    try:
        logger.info("Running Primary PaddleOCR Engine (Optimized High-Speed)...")
        prep_img = enhance_document_image(np_img)
        
        # High-Resolution Image Resizing (Limit max dimension to 2400px to preserve word spaces)
        h, w = prep_img.shape[:2]
        max_dim = 2400
        if max(h, w) > max_dim:
            scale_factor = max_dim / float(max(h, w))
            prep_img = cv2.resize(prep_img, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_AREA)

        result = p_engine.ocr(prep_img)
        if not result:
            return ""

        words_data = []
        for item in result:
            page_dict = item if isinstance(item, dict) else (item[0] if isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict) else None)
            if page_dict:
                rec_texts = page_dict.get("rec_texts", [])
                rec_polys = page_dict.get("rec_polys", []) or page_dict.get("dt_polys", [])
                rec_scores = page_dict.get("rec_scores", [])
                if rec_texts:
                    for idx, txt in enumerate(rec_texts):
                        txt_str = str(txt).strip()
                        if not txt_str:
                            continue
                        poly = rec_polys[idx] if idx < len(rec_polys) else []
                        bbox_list = [[int(pt[0]), int(pt[1])] for pt in poly] if len(poly) > 0 else [[0,0],[0,0],[0,0],[0,0]]
                        conf = float(rec_scores[idx]) if idx < len(rec_scores) else 1.0
                        words_data.append({
                            'text': txt_str,
                            'bbox': bbox_list,
                            'confidence': conf
                        })
            elif isinstance(item, list):
                for sub_item in item:
                    if isinstance(sub_item, (list, tuple)) and len(sub_item) >= 2:
                        poly = sub_item[0]
                        txt_info = sub_item[1]
                        txt_str = str(txt_info[0]).strip() if isinstance(txt_info, (list, tuple)) and len(txt_info) > 0 else str(txt_info).strip()
                        if txt_str:
                            bbox_list = [[int(pt[0]), int(pt[1])] for pt in poly] if len(poly) > 0 else [[0,0],[0,0],[0,0],[0,0]]
                            conf = float(txt_info[1]) if isinstance(txt_info, (list, tuple)) and len(txt_info) > 1 else 1.0
                            words_data.append({
                                'text': txt_str,
                                'bbox': bbox_list,
                                'confidence': conf
                            })

        if not words_data:
            return ""

        return group_words_into_lines_spatially(words_data)
    except Exception as e:
        logger.error(f"Error executing PaddleOCR primary engine: {e}")
        return ""

def convert_pdf_to_images(pdf_bytes, scale=2):
    logger.info("Converting PDF pages to images using pypdfium2")
    images = []
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        for i in range(len(pdf)):
            page = pdf[i]
            pil_image = page.render(scale=scale).to_pil()
            images.append(pil_image)
        logger.info(f"Successfully converted {len(images)} PDF pages.")
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        raise e
    return images

def group_words_into_lines_spatially(words_data, y_tolerance=4):
    """
    Groups OCR word bounding boxes by spatial 2D coordinates:
    1. Sorts all word bounding boxes primarily by top Y-coordinate.
    2. Clusters words into the same horizontal line if their Y-coordinates overlap tightly within y_tolerance.
    3. Within each horizontal line, sorts words left-to-right by X-coordinate.
    4. Reconstructs pristine horizontal lines matching visual document layout.
    """
    if not words_data:
        return ""

    heights = []
    for w in words_data:
        bbox = w['bbox']
        h = abs(bbox[2][1] - bbox[0][1])
        if h > 0:
            heights.append(h)
            
    avg_h = sum(heights) / len(heights) if heights else 15
    dynamic_tolerance = max(y_tolerance, avg_h * 0.3)

    sorted_words = sorted(words_data, key=lambda item: item['bbox'][0][1])

    lines = []
    for w in sorted_words:
        bbox = w['bbox']
        w_y = bbox[0][1]
        
        placed = False
        for line in lines:
            line_y = sum(item['bbox'][0][1] for item in line) / len(line)
            if abs(w_y - line_y) <= dynamic_tolerance:
                line.append(w)
                placed = True
                break
                
        if not placed:
            lines.append([w])

    reconstructed_lines = []
    for line in lines:
        sorted_line = sorted(line, key=lambda item: item['bbox'][0][0])
        line_text = " ".join(item['text'].strip() for item in sorted_line if item['text'].strip())
        if line_text:
            reconstructed_lines.append(line_text)

    return "\n".join(reconstructed_lines)

def run_ocr_on_image(image_input, languages=None):
    ocr_input = image_input
    if isinstance(image_input, Image.Image):
        ocr_input = np.array(image_input.convert('RGB'))
    elif isinstance(image_input, bytes):
        pil_img = Image.open(io.BytesIO(image_input)).convert('RGB')
        ocr_input = np.array(pil_img)

    # 1. Try PaddleOCR as Primary Engine (Higher Accuracy & Zero Typo)
    paddle_text = run_paddle_ocr_fallback(ocr_input)
    if paddle_text and len(paddle_text.strip()) >= 10:
        logger.info("Successfully extracted text via Primary PaddleOCR Engine!")
        return {
            'text': paddle_text,
            'words': []
        }

    # 2. Fallback to EasyOCR Engine
    reader = get_ocr_reader(languages)
    logger.info("Running EasyOCR on image input (Fallback Engine)...")
    results = reader.readtext(ocr_input)
    
    words_data = []
    for bbox, text, confidence in results:
        bbox_list = [[int(pt[0]), int(pt[1])] for pt in bbox]
        words_data.append({
            'text': text,
            'bbox': bbox_list,
            'confidence': float(confidence)
        })
    
    concatenated_text = group_words_into_lines_spatially(words_data)
    return {
        'text': concatenated_text,
        'words': words_data
    }

def extract_text_from_image(image_input, languages=None):
    if isinstance(image_input, str) and os.path.exists(image_input):
        with open(image_input, 'rb') as f:
            b = f.read()
        res = process_document(b, image_input, languages)
    elif isinstance(image_input, bytes):
        res = process_document(image_input, "upload_file.jpg", languages)
    else:
        res = run_ocr_on_image(image_input, languages)
    return res['text'] if isinstance(res, dict) else str(res)

def process_document(file_bytes, file_name, languages=None):
    ext = os.path.splitext(file_name)[1].lower()
    if ext == '.pdf':
        try:
            images = convert_pdf_to_images(file_bytes)
        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
            return {'text': f"Error parsing PDF: {str(e)}", 'words': [], 'pages': []}
        
        combined_text_parts = []
        all_words = []
        pages_data = []
        
        for idx, img in enumerate(images):
            page_res = run_ocr_on_image(img, languages)
            combined_text_parts.append(f"--- Page {idx + 1} ---\n{page_res['text']}")
            all_words.extend(page_res['words'])
            pages_data.append({
                'page_number': idx + 1,
                'text': page_res['text'],
                'words': page_res['words']
            })
            
        return {
            'text': "\n\n".join(combined_text_parts),
            'words': all_words,
            'pages': pages_data
        }
    else:
        try:
            pil_img = Image.open(io.BytesIO(file_bytes))
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            res = run_ocr_on_image(pil_img, languages)
            return {
                'text': res['text'],
                'words': res['words'],
                'pages': [{
                    'page_number': 1,
                    'text': res['text'],
                    'words': res['words']
                }]
            }
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            return {'text': f"Error parsing image: {str(e)}", 'words': [], 'pages': []}
