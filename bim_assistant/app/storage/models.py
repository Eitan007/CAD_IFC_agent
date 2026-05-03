"""
app/storage/models.py
SQLAlchemy ORM models (PostgreSQL backend).

The `properties` column uses JSONB to store arbitrary psets without
schema migrations for every new IFC property set.
"""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import (
    String, Float, DateTime, Text, Boolean,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_file: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    parse_warnings: Mapped[list] = mapped_column(JSONB, default=list)
    element_count: Mapped[int] = mapped_column(default=0)

    elements: Mapped[list["Element"]] = relationship("Element", back_populates="project", lazy="selectin")


class Element(Base):
    __tablename__ = "elements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    ifc_guid: Mapped[str | None] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    # Geometry
    volume: Mapped[float | None] = mapped_column(Float)
    area: Mapped[float | None] = mapped_column(Float)
    length: Mapped[float | None] = mapped_column(Float)
    bbox_min_x: Mapped[float | None] = mapped_column(Float)
    bbox_min_y: Mapped[float | None] = mapped_column(Float)
    bbox_min_z: Mapped[float | None] = mapped_column(Float)
    bbox_max_x: Mapped[float | None] = mapped_column(Float)
    bbox_max_y: Mapped[float | None] = mapped_column(Float)
    bbox_max_z: Mapped[float | None] = mapped_column(Float)

    # Material & location
    material: Mapped[str | None] = mapped_column(String(128), index=True)
    material_volume: Mapped[float | None] = mapped_column(Float)
    storey: Mapped[str | None] = mapped_column(String(128))
    room: Mapped[str | None] = mapped_column(String(128))
    located_in: Mapped[str | None] = mapped_column(String(64))
    contained_by: Mapped[str | None] = mapped_column(String(64))

    # Relationships stored as JSONB arrays of ids
    connected_to: Mapped[list] = mapped_column(JSONB, default=list)
    contains: Mapped[list] = mapped_column(JSONB, default=list)

    # Arbitrary properties
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="elements")

    __table_args__ = (Index("ix_elements_project_type", "project_id", "type"),)
