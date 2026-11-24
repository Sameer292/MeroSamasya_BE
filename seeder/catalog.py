from dataclasses import dataclass
from os import environ

from app.schemas.enum import IssueStatusEnum

HETAUDA = "हेटौंडा उप-महानगरपालिका"
MAKWANPUR = "मकवानपुर"
ADMIN_EMAIL = environ.get("SEED_DEMO_ADMIN_EMAIL", "admin@gmail.com")
APPROVED_COUNT = 80
REPORTER_COUNT = 60

FIRST_NAMES = (
    "Ram", "Sita", "Asha", "Bikash", "Deepa", "Kiran", "Maya", "Nabin", "Rita", "Suman",
)
LAST_NAMES = (
    "Shrestha", "Thapa", "Tamang", "Gurung", "Karki", "Bhandari", "Rai", "Lama", "Poudel", "Magar",
)

# These are demo pins within the bundled Hetauda polygon.
SITES = (
    ("Town Centre", 27.428, 85.032),
    ("West Market", 27.422, 85.027),
    ("North Market", 27.436, 85.040),
    ("Industrial Area", 27.410, 85.036),
    ("East Bus Route", 27.417, 85.049),
    ("Northwest Residential Area", 27.445, 85.019),
    ("Southwest Residential Area", 27.410, 85.017),
    ("Eastern Residential Area", 27.430, 85.055),
    ("Southeast Road", 27.414, 85.064),
)

STATUS_COUNTS = (
    (IssueStatusEnum.open, 60),
    (IssueStatusEnum.in_progress, 23),
    (IssueStatusEnum.resolved, 16),
    (IssueStatusEnum.closed, 9),
)


@dataclass(frozen=True)
class ReportTemplate:
    category: str
    photo: str
    title: str
    details: str


REPORT_TEMPLATES = (
    ReportTemplate("Roads & Transport", "pothole", "Deep pothole in the traffic lane",
                   "Motorcycles swerve into oncoming traffic to avoid the damaged patch."),
    ReportTemplate("Roads & Transport", "asphalt", "Cracked road beside the main junction",
                   "The road surface is breaking apart and loose gravel is collecting near the turn."),
    ReportTemplate("Roads & Transport", "pothole", "Pothole near the bus pickup point",
                   "Buses need to pull out into the lane to avoid the hole when picking up passengers."),
    ReportTemplate("Water & Drainage", "flood", "Rainwater pooling at the crossing",
                   "Water remains across the crossing after rain and forces pedestrians into traffic."),
    ReportTemplate("Water & Drainage", "flood", "Storm drain overflowing",
                   "Runoff backs up onto the roadside during rain. Please check the drain inlet."),
    ReportTemplate("Water & Drainage", "flood", "Standing water by the access road",
                   "A shallow pool blocks access after heavy rain and remains well into the next day."),
    ReportTemplate("Waste & Sanitation", "waste", "Uncollected waste beside the lane",
                   "Bags have built up at the roadside collection point since the last pickup."),
    ReportTemplate("Waste & Sanitation", "waste", "Rubbish blocking the footpath",
                   "Loose packaging and bags have spread across the route used by pedestrians."),
    ReportTemplate("Waste & Sanitation", "waste", "Overflow at the collection point",
                   "The collection spot is full and rubbish is spreading toward nearby entrances."),
    ReportTemplate("Public Infrastructure", "sidewalk", "Broken pavement at the corner",
                   "An uneven pavement slab makes the corner difficult to use with a pram or wheelchair."),
    ReportTemplate("Public Infrastructure", "sidewalk", "Raised slab on the walking route",
                   "A raised edge on the footpath is a trip hazard when the area is busy."),
    ReportTemplate("Public Safety & Health", "sidewalk", "Trip hazard at the pedestrian approach",
                   "The walking surface is uneven just before the crossing and needs a temporary marker."),
)
