from dataclasses import dataclass
from itertools import product
from os import environ

from app.schemas.enum import IssueStatusEnum
from seeder.reports import REPORTS_BY_SITE

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
    (IssueStatusEnum.open, 10),
    (IssueStatusEnum.in_progress, 15),
    (IssueStatusEnum.resolved, 66),
    (IssueStatusEnum.closed, 17),
)


@dataclass(frozen=True)
class LegacyReportTemplate:
    category: str
    photo: str
    title: str
    details: str


LEGACY_REPORT_TEMPLATES = (
    LegacyReportTemplate("Roads & Transport", "pothole", "Deep pothole in the traffic lane",
                   "Motorcycles swerve into oncoming traffic to avoid the damaged patch."),
    LegacyReportTemplate("Roads & Transport", "asphalt", "Cracked road beside the main junction",
                   "The road surface is breaking apart and loose gravel is collecting near the turn."),
    LegacyReportTemplate("Roads & Transport", "pothole", "Pothole near the bus pickup point",
                   "Buses need to pull out into the lane to avoid the hole when picking up passengers."),
    LegacyReportTemplate("Water & Drainage", "flood", "Rainwater pooling at the crossing",
                   "Water remains across the crossing after rain and forces pedestrians into traffic."),
    LegacyReportTemplate("Water & Drainage", "flood", "Storm drain overflowing",
                   "Runoff backs up onto the roadside during rain. Please check the drain inlet."),
    LegacyReportTemplate("Water & Drainage", "flood", "Standing water by the access road",
                   "A shallow pool blocks access after heavy rain and remains well into the next day."),
    LegacyReportTemplate("Waste & Sanitation", "waste", "Uncollected waste beside the lane",
                   "Bags have built up at the roadside collection point since the last pickup."),
    LegacyReportTemplate("Waste & Sanitation", "waste", "Rubbish blocking the footpath",
                   "Loose packaging and bags have spread across the route used by pedestrians."),
    LegacyReportTemplate("Waste & Sanitation", "waste", "Overflow at the collection point",
                   "The collection spot is full and rubbish is spreading toward nearby entrances."),
    LegacyReportTemplate("Public Infrastructure", "sidewalk", "Broken pavement at the corner",
                   "An uneven pavement slab makes the corner difficult to use with a pram or wheelchair."),
    LegacyReportTemplate("Public Infrastructure", "sidewalk", "Raised slab on the walking route",
                   "A raised edge on the footpath is a trip hazard when the area is busy."),
    LegacyReportTemplate("Public Safety & Health", "sidewalk", "Trip hazard at the pedestrian approach",
                   "The walking surface is uneven just before the crossing and needs a temporary marker."),
)


def demo_report_index():
    """Match both the current catalog and demo databases seeded before it."""
    current = (
        (report.title, report.description, f"{site}, Hetauda, Makwanpur")
        for site, *_ in SITES
        for report in REPORTS_BY_SITE[site]
    )
    legacy = (
        (f"{template.title} | {site}", template.details, f"{site}, Hetauda, Makwanpur")
        for (site, *_), template in product(SITES, LEGACY_REPORT_TEMPLATES)
    )
    return {**{key: index for index, key in enumerate(legacy)},
            **{key: index for index, key in enumerate(current)}}
