"""Centrale gebruikersdatabase — modellen voor de Medewerkers-app.

Lezen gaat via de read-only rol (`DATABASE_URL` / `portal`). Voor de firma-koppeling
(werkgever + diensten) bestaat een aparte, **smalle schrijf-engine**
(`APPPORTAL_WRITE_URL` / `medewerker_writer`) die enkel `persoon.werkgever_firma_id`
en de koppeltabel mag wijzigen. Bron van waarheid + volledige veldenlijst: ONTWERP §3.
"""
import os
import uuid

from sqlalchemy import Column, ForeignKey, String, Table, create_engine
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
WRITE_URL = os.environ.get("APPPORTAL_WRITE_URL", "").strip()

# Read-engine draagt de hele app; write-engine bestaat alleen als APPPORTAL_WRITE_URL
# gezet is. Zo blijft alles read-only draaien tot de schrijfrol geconfigureerd is.
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=5,
                       pool_pre_ping=True, pool_recycle=1800) if DATABASE_URL else None
Session = sessionmaker(bind=engine) if engine else None

write_engine = create_engine(WRITE_URL, pool_size=3, max_overflow=3,
                             pool_pre_ping=True, pool_recycle=1800) if WRITE_URL else None
WriteSession = sessionmaker(bind=write_engine) if write_engine else None


class Base(DeclarativeBase):
    pass


class Afdeling(Base):
    __tablename__ = "afdeling"
    __table_args__ = {"schema": "kern"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    naam: Mapped[str] = mapped_column(String(80))
    actief: Mapped[bool] = mapped_column()


class Firma(Base):
    __tablename__ = "firma"
    __table_args__ = {"schema": "kern"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    naam: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(16))
    land: Mapped[str] = mapped_column(String(60))
    actief: Mapped[bool] = mapped_column()


# Koppeltabel "medewerker verricht diensten voor firma" (veel-op-veel).
persoon_dienstfirma = Table(
    "persoon_dienstfirma", Base.metadata,
    Column("persoon_id", ForeignKey("kern.persoon.id"), primary_key=True),
    Column("firma_id", ForeignKey("kern.firma.id"), primary_key=True),
    schema="kern",
)


class Persoon(Base):
    __tablename__ = "persoon"
    __table_args__ = {"schema": "kern"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    hr_nummer: Mapped[str | None] = mapped_column(String(32))
    voornaam: Mapped[str] = mapped_column(String(120))
    achternaam: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    afdeling_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kern.afdeling.id"))
    rol: Mapped[str] = mapped_column(String(20))
    functie: Mapped[str | None] = mapped_column(String(120))
    locatie: Mapped[str] = mapped_column(String(60))
    authentik_sub: Mapped[str | None] = mapped_column(String(64))
    authentik_username: Mapped[str | None] = mapped_column(String(150))
    in_dienst: Mapped[bool] = mapped_column()
    werkgever_firma_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("kern.firma.id"))

    afdeling: Mapped["Afdeling"] = relationship(lazy="joined")
    werkgever: Mapped["Firma | None"] = relationship(
        foreign_keys=[werkgever_firma_id], lazy="joined")
    dienst_firmas: Mapped[list["Firma"]] = relationship(
        secondary=persoon_dienstfirma, lazy="selectin", order_by="Firma.naam")

    @property
    def volledige_naam(self) -> str:
        return f"{self.voornaam} {self.achternaam or ''}".strip()
