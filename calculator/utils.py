import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

# A phone photo of a bill is routinely 3-8 MB straight out of the camera.
# Downscaling and re-encoding before it ever touches disk (or an email
# attachment) keeps storage and email size small without a visible quality
# loss for what is just a reference photo of a paper bill.
MAX_DIMENSION = 1600
JPEG_QUALITY = 78


def compress_bill_image(uploaded_file):
    """Downscale and re-encode an uploaded bill photo as a compact JPEG.

    Returns a new ContentFile named "<original-basename>.jpg". Raises
    ValueError if the file isn't a readable image, so callers can turn that
    into a normal field validation error.
    """
    uploaded_file.seek(0)
    try:
        image = Image.open(uploaded_file)
        image.load()
    except UnidentifiedImageError as exc:
        raise ValueError("Could not read the uploaded image.") from exc

    image = ImageOps.exif_transpose(image)  # respect phone camera orientation
    image = image.convert("RGB")

    if max(image.size) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)

    base_name = uploaded_file.name.rsplit(".", 1)[0]
    return ContentFile(buffer.getvalue(), name=f"{base_name}.jpg")
