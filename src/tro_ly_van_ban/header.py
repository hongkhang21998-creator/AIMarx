"""Trích số ký hiệu, cơ quan ban hành, ngày ban hành bằng quy tắc thể thức.

Ba trường này theo thể thức văn bản hành chính (Nghị định 30/2020/NĐ-CP):
"Số: 145/UBND-VP", "Giả Lập A, ngày 05 tháng 9 năm 2026", tên cơ quan viết hoa
ở góc trên trái. Đo trên bộ chấm, model 0,6B lấy sai hoặc bỏ trống gần hết, có
lúc bịa ("Bộ Công an"), trong khi quy tắc lấy đúng.

Tính chất quan trọng nhất không phải độ đúng mà là **không bịa**: mọi giá trị là
một đoạn cắt nguyên văn từ nguồn, quote là dòng chứa nó. Không khớp quy tắc thì
trả None để người dùng tự điền — không đoán, không lấy từ model.

Xử lý ba dạng khối của parser: TXT (mỗi dòng một khối), PDF (cả trang một khối
nhiều dòng), DOCX (phần đầu thường là bảng hai cột, parser ghép ô bằng " | " và
đặt bảng SAU các đoạn văn).
"""
import re

HEAD_BLOCKS = 8
NATIONAL = re.compile(r"CỘNG\s+HÒA\s+XÃ\s+HỘI\s+CHỦ\s+NGHĨA\s+VIỆT\s+NAM", re.I)
NUMBER = re.compile(r"^\s*Số\s*:?\s*(\d[\w.]*/[\w./-]*\w)", re.I)
DATE = re.compile(r"^[^,]{1,60},\s*(ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}|ngày\s+\d{1,2}/\d{1,2}/\d{4})", re.I)
# Dong viet hoa khong phai ten co quan: quoc hieu, tieu ngu, do khan/mat, ten loai van ban.
NOT_AGENCY = re.compile(
    r"^(CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM|ĐỘC LẬP\s*-\s*TỰ DO\s*-\s*HẠNH PHÚC|KHẨN|THƯỢNG KHẨN|HỎA TỐC.*|MẬT|TỐI MẬT|"
    r"TUYỆT MẬT|CÔNG VĂN|THÔNG BÁO|BÁO CÁO|GIẤY MỜI|TỜ TRÌNH|KẾ HOẠCH|QUYẾT ĐỊNH|NGHỊ QUYẾT|CHỈ THỊ|HƯỚNG DẪN|"
    r"BIÊN BẢN|CÔNG ĐIỆN|THÔNG TƯ|NGHỊ ĐỊNH|CHƯƠNG TRÌNH|PHƯƠNG ÁN|ĐỀ ÁN|DỰ THẢO|GIẤY GIỚI THIỆU|PHIẾU GỬI)$", re.I)


def _segments(block):
    """Các đoạn chữ liền mạch trong một khối: theo dòng, rồi theo ô bảng " | "."""
    for line in block["text"].split("\n"):
        for cell in line.split(" | "):
            if cell.strip():
                yield cell.strip()


def _candidates(blocks):
    # Bang dau tien cua DOCX thuong la khung the thuc, nhung parser xep bang SAU doan van.
    # Xet no truoc, neu khong mot dong viet hoa trong than van ban se bi nhan nham la co quan.
    frame = [b for b in blocks if str(b.get("location", "")).startswith("Bảng 1,")]
    head = frame + [b for b in blocks[:HEAD_BLOCKS] if b not in frame]
    for block in head:
        for seg in _segments(block):
            yield block, seg


def _evidence(block, value, quote):
    # Khong dung assert: python -O bo assert, ma day la bao dam "khong bia".
    if not value or value not in quote or quote not in block["text"]:
        return None
    return {"value": value, "block_id": block["id"], "quote": quote}


def _is_upper_line(seg):
    letters = [c for c in seg if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.8


def extract_header(blocks: list[dict]) -> dict:
    """Trả {"number", "agency", "document_date"}, mỗi mục là evidence dict hoặc None."""
    number = date = None
    agency_lines = []
    header_ended = False
    for block, seg in _candidates(blocks):
        # Dong gop hai cot tu PDF co the chua ca so ky hieu lan ngay, nen xet ca hai.
        matched = False
        m = NUMBER.match(seg)
        if m:
            matched = True
            if number is None:
                number = _evidence(block, m.group(1), seg)
        m = DATE.match(seg)
        if m:
            matched = True
            if date is None:
                date = _evidence(block, m.group(1), seg)
        if matched:
            header_ended = True
            continue
        if header_ended or not _is_upper_line(seg):
            continue
        # Dong gop hai cot tu PDF: "UBND HUYỆN A CỘNG HÒA XÃ HỘI..." -> lay phan truoc quoc hieu.
        national = NATIONAL.search(seg)
        name = seg[:national.start()].strip() if national else seg
        if name and not NOT_AGENCY.match(name) and _is_upper_line(name):
            agency_lines.append((block, name, seg))
    agency = None
    if agency_lines:
        # Co quan chu quan o tren, co quan ban hanh o duoi (ND 30/2020): lay dong cuoi.
        block, name, seg = agency_lines[-1]
        agency = _evidence(block, name, seg)
    return {"number": number, "agency": agency, "document_date": date}
