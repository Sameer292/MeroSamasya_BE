from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base


class PhotoObject(Base):
    __tablename__ = "PhotoObjects"

    url = Column(Text, primary_key=True)
    object_key = Column(String, nullable=False)
    cloud = Column(String, nullable=True)
    image_format = Column(String, nullable=True)
    # Pending uploads have a lease, active photos have NULL, retired photos are due now.
    delete_after = Column(DateTime(timezone=True), nullable=True, index=True)
