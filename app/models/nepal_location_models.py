from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base

from app.schemas.enum import LocalLevelType


class Province(Base):
    __tablename__ = "provinces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    districts = relationship(
        "District",
        back_populates="province",
        cascade="all, delete",
    )


class District(Base):
    __tablename__ = "districts"

    __table_args__ = (UniqueConstraint("name", "province_id"),)

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    province_id = Column(
        Integer,
        ForeignKey("provinces.id", ondelete="CASCADE"),
        nullable=False,
    )

    province = relationship(
        "Province",
        back_populates="districts",
    )

    local_levels = relationship(
        "LocalLevel",
        back_populates="district",
        cascade="all, delete",
    )


class LocalLevel(Base):
    __tablename__ = "local_levels"

    __table_args__ = (UniqueConstraint("name", "district_id"),)

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    type = Column(
        Enum(LocalLevelType, name="local_level_type_enum"),
        nullable=False,
    )

    district_id = Column(
        Integer,
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
    )

    district = relationship(
        "District",
        back_populates="local_levels",
    )
