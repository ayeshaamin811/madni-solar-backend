from backend.image_utils import compress_image

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
    return compress_image(uploaded_file, max_dimension=MAX_DIMENSION, quality=JPEG_QUALITY)
