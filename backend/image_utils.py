import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

# Shared by calculator (bill photos, compressed during upload validation) and
# solar_panels (brand/product photos, compressed on model save).


def compress_image(uploaded_file, *, max_dimension=1600, quality=80):
    """Downscale and re-encode an uploaded image as a compact JPEG.

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

    if max(image.size) > max_dimension:
        image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)

    base_name = uploaded_file.name.rsplit(".", 1)[0]
    return ContentFile(buffer.getvalue(), name=f"{base_name}.jpg")


def compress_field_file(field_file, *, max_dimension=1600, quality=80):
    """Compress a model ImageField's pending upload, in place-ish.

    Used from a model's save() to shrink admin-uploaded photos without
    touching every call site. A no-op for a file that's already stored
    (FieldFile._committed) so editing an unrelated field doesn't
    re-compress - re-compressing an already-compressed JPEG on every save
    would keep degrading it. Falls back to the original file if it can't be
    read as an image, so ImageField's own validation is what reports the
    error to the admin form.
    """
    if not field_file or getattr(field_file, "_committed", True):
        return field_file
    try:
        return compress_image(field_file, max_dimension=max_dimension, quality=quality)
    except ValueError:
        return field_file
