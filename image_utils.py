import os
from PIL import Image
from werkzeug.utils import secure_filename
from datetime import datetime

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads', 'praxis')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_WIDTH = 1600
WEBP_QUALITY = 85


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def optimize_and_save(file_storage, prefix, praxis_id):
    if not file_storage or not file_storage.filename or not allowed_file(file_storage.filename):
        return None

    file_storage.seek(0, 2)
    file_size = file_storage.tell()
    file_storage.seek(0)

    if file_size > MAX_FILE_SIZE:
        return None

    try:
        img = Image.open(file_storage)

        has_alpha = img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info)

        if has_alpha:
            img = img.convert('RGBA')
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / img.width
            new_height = int(img.height * ratio)
            img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = secure_filename(f"{prefix}_{praxis_id}_{timestamp}.webp")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        img.save(filepath, 'WEBP', quality=WEBP_QUALITY, method=4)

        return f"/static/uploads/praxis/{filename}"
    except Exception:
        return None
