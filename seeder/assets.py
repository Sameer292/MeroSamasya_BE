import io
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from urllib.parse import quote
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core import storage
from app.models.photo_storage import PhotoObject
from app.services.photo_storage import photo_url

PHOTO_FILES = {
    "pothole": "Marked_Pothole.jpg",
    "asphalt": "Worn_cracked_asphalt_pavement.jpg",
    "road_detail": "Hole_in_the_road_-_Flickr_-_Robbie1.jpg",
    "flood": "Flooded_street_in_Sacramento_with_stop_sign_and_whirlpool.jpg",
    "flood_crossing": "Flooded_street_in_town.jpg",
    "flood_traffic": "Flooded_street_and_vehicles.JPG",
    "waste": "Street_Garbage.jpg",
    "sidewalk": "Cracked_sidewalk_1.jpg",
}
DOCUMENT_TITLES = {
    "selfie": "Selfie",
    "front": "Citizenship document (front)",
    "back": "Citizenship document (back)",
}
AVATAR_COUNT = 16
MAX_DOWNLOAD = 12 * 1024 * 1024


def issue_photo_keys(primary: str, index: int) -> tuple[str, ...]:
    alternatives = {
        "pothole": ("asphalt", "road_detail"),
        "asphalt": ("road_detail", "pothole"),
        "flood": ("flood_crossing", "flood_traffic"),
    }.get(primary, ())
    total = (1, 2, 3, 2, 1, 3, 2)[index % 7]
    return (primary, *alternatives[:total - 1])


def commons_url(filename: str) -> str:
    digest = md5(filename.encode(), usedforsecurity=False).hexdigest()
    name = quote(filename)
    path = f"{digest[0]}/{digest[:2]}/{name}/960px-{name}"
    return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{path}"


def jpeg(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=86, optimize=True)
    return output.getvalue()


def download_photo(url: str) -> bytes:
    request = Request(url, headers={
        "User-Agent": "MeroSamasyaDemoSeeder/1.0 (https://github.com/Sameer292/MeroSamasya_BE)",
        "Referer": "https://commons.wikimedia.org/",
    })
    with urlopen(request, timeout=25) as response:
        content = response.read(MAX_DOWNLOAD + 1)
    if len(content) > MAX_DOWNLOAD:
        raise ValueError(f"Demo image exceeds download limit: {url}")
    with Image.open(io.BytesIO(content)) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((1100, 850))
        return jpeg(image)


def download_assets() -> tuple[dict[str, bytes], list[bytes]]:
    photo_urls = [commons_url(name) for name in PHOTO_FILES.values()]
    avatar_urls = [
        f"https://api.dicebear.com/9.x/lorelei/png?seed=hetauda-demo-{index}&size=256"
        for index in range(AVATAR_COUNT)
    ]
    with ThreadPoolExecutor(max_workers=4) as workers:
        sources = list(workers.map(download_photo, photo_urls + avatar_urls))
    count = len(photo_urls)
    return dict(zip(PHOTO_FILES, sources[:count], strict=True)), sources[count:]


def sample_document(kind: str, name: str, reference: str, avatar: bytes) -> bytes:
    image = Image.new("RGB", (760, 440), "#eff6ff")
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 744, 424), outline="#244671", width=4)
    draw.text((38, 38), "DEMO ONLY - NOT A VALID ID", fill="#9b2424", font=ImageFont.load_default(size=32))
    draw.text((38, 105), DOCUMENT_TITLES[kind], fill="#244671", font=ImageFont.load_default(size=23))
    draw.text((38, 172), name, fill="#182638", font=ImageFont.load_default(size=22))
    draw.text((38, 220), reference, fill="#182638", font=ImageFont.load_default(size=22))
    draw.text((38, 270), "Fictional record for a software showcase", fill="#244671")
    if kind != "back":
        with Image.open(io.BytesIO(avatar)) as portrait:
            image.paste(ImageOps.fit(portrait, (168, 168)), (535, 125))
    return jpeg(image)


class DemoPhotos:
    def __init__(self):
        self.files: list[tuple[str, str, bytes]] = []

    def add(self, db, kind: str, content: bytes) -> str:
        name = storage.local_name("image/jpeg")
        url = photo_url(kind, name)
        db.add(PhotoObject(url=url, object_key=f"{kind}/{name}"))
        self.files.append((kind, name, content))
        return url

    def write(self) -> None:
        for kind, name, content in self.files:
            storage.write_local(content, kind, name)

    def discard(self) -> None:
        for kind, name, _ in self.files:
            storage.delete_local(kind, name)
