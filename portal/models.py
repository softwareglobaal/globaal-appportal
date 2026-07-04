"""Centrale gebruikersdatabase — read-only modellen voor de portal.

De portal leest `kern.persoon`/`kern.afdeling` uit de gedeelde `appportal`-database
voor de medewerkerspagina. Schrijven (login-binding, offboarding) komt later; v1 is
puur lezend. Bron van waarheid en volledige veldenlijst: ONTWERP §3.
"""
import os
import uuid

from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Engine/Session bestaan alleen als er een DATABASE_URL is. Zo blijft de portal
# starten (en de rest werken) ook als de medewerkers-feature nog niet is aangezet.
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=5,
                       pool_pre_ping=True, pool_recycle=1800) if DATABASE_URL else None
Session = sessionmaker(bind=engine) if engine else None


class Base(DeclarativeBase):
    pass


class Afdeling(Base):
    __tablename__ = "afdeling"
    __table_args__ = {"schema": "kern"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    naam: Mapped[str] = mapped_column(String(80))
    actief: Mapped[bool] = mapped_column()


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
    authentik_sub: Mapped[str | None] = mapped_column(String(64))
    in_dienst: Mapped[bool] = mapped_column()

    afdeling: Mapped["Afdeling"] = relationship(lazy="joined")

    @property
    def volledige_naam(self) -> str:
        return f"{self.voornaam} {self.achternaam or ''}".strip()
