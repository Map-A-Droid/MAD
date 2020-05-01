from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    SmallInteger,
    Index,
    create_engine,
    Integer,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import BIGINT, DOUBLE, TINYINT, LONGTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import DateTime

Base = declarative_base()
engine = create_engine(
    "mysql://mad:pass@localhost:3306/mad?charset=utf8",
    pool_recycle=150,
    pool_size=100,
    pool_pre_ping=True,
)


class Mon(Base):
    __tablename__ = "pokemon"

    encounter_id = Column(BIGINT(unsigned=True), primary_key=True)
    spawnpoint_id = Column(BIGINT(unsigned=True), nullable=False)
    pokemon_id = Column(SmallInteger, nullable=False)
    latitude = Column(DOUBLE(asdecimal=False), nullable=False)
    longitude = Column(DOUBLE(asdecimal=False), nullable=False)
    disappear_time = Column(DateTime, nullable=False)
    individual_attack = Column(SmallInteger)
    individual_defense = Column(SmallInteger)
    individual_stamina = Column(SmallInteger)
    move_1 = Column(SmallInteger)
    move_2 = Column(SmallInteger)
    cp = Column(SmallInteger)
    cp_multiplier = Column(Float)
    weight = Column(Float)
    height = Column(Float)
    gender = Column(SmallInteger)
    form = Column(SmallInteger)
    costume = Column(SmallInteger)
    catch_prob_1 = Column(DOUBLE(asdecimal=False))
    catch_prob_2 = Column(DOUBLE(asdecimal=False))
    catch_prob_3 = Column(DOUBLE(asdecimal=False))
    rating_attack = Column(String(length=2, collation="utf8mb4_unicode_ci"))
    rating_defense = Column(String(length=2, collation="utf8mb4_unicode_ci"))
    weather_boosted_condition = Column(SmallInteger)
    last_modified = Column(DateTime)

    __table_args__ = (
        Index("pokemon_spawnpoint_id", "spawnpoint_id"),
        Index("pokemon_pokemon_id", "pokemon_id"),
        Index("pokemon_last_modified", "last_modified"),
        Index("pokemon_latitude_longitude", "latitude", "longitude"),
        Index("pokemon_disappear_time_pokemon_id", "disappear_time", "pokemon_id"),
    )


class Gym(Base):
    __tablename__ = "gym"

    gym_id = Column(String(length=50, collation="utf8mb4_unicode_ci"), primary_key=True)
    team_id = Column(SmallInteger, default=0, nullable=False)
    guard_pokemon_id = Column(SmallInteger, default=0, nullable=False)
    slots_available = Column(SmallInteger, default=6, nullable=False)
    enabled = Column(TINYINT, default=1, nullable=False)
    latitude = Column(DOUBLE(asdecimal=False), nullable=False)
    longitude = Column(DOUBLE(asdecimal=False), nullable=False)
    total_cp = Column(SmallInteger, default=0, nullable=False)
    is_in_battle = Column(TINYINT, default=0, nullable=False)
    gender = Column(SmallInteger)
    form = Column(SmallInteger)
    costume = Column(SmallInteger)
    weather_boosted_condition = Column(SmallInteger)
    shiny = Column(TINYINT)
    last_modified = Column(DateTime, default=datetime.utcnow(), nullable=False)
    last_scanned = Column(DateTime, default=datetime.utcnow(), nullable=False)
    is_ex_raid_eligible = Column(TINYINT, default=0, nullable=False)

    gym_details = relationship(
        "GymDetails", uselist=False, backref="gym", lazy="joined", cascade="delete"
    )

    __table_args__ = (
        Index("gym_last_modified", "last_modified"),
        Index("gym_last_scanned", "last_scanned"),
        Index("gym_latitude_longitude", "latitude", "longitude"),
    )


class GymDetails(Base):
    __tablename__ = "gymdetails"

    gym_id = Column(
        String(length=50, collation="utf8mb4_unicode_ci"),
        ForeignKey("gym.gym_id", name="fk_gd_gym_id"),
        primary_key=True,
    )
    name = Column(String(length=191, collation="utf8mb4_unicode_ci"), nullable=False)
    description = Column(LONGTEXT(collation="utf8mb4_unicode_ci"))
    url = Column(String(length=191, collation="utf8mb4_unicode_ci"), nullable=False)
    last_scanned = Column(DateTime, default=datetime.utcnow(), nullable=False)


class Raid(Base):
    __tablename__ = "raid"

    gym_id = Column(String(length=50, collation="utf8mb4_unicode_ci"), primary_key=True)
    level = Column(Integer, nullable=False)
    spawn = Column(DateTime, nullable=False)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    pokemon_id = Column(SmallInteger)
    cp = Column(Integer)
    move_1 = Column(SmallInteger)
    move_2 = Column(SmallInteger)
    last_scanned = Column(DateTime, nullable=False)
    form = Column(SmallInteger)
    is_exclusive = Column(TINYINT)
    gender = Column(TINYINT)
    costume = Column(TINYINT)

    __table_args__ = (
        Index("raid_level", "level"),
        Index("raid_spawn", "spawn"),
        Index("raid_start", "start"),
        Index("raid_end", "end"),
        Index("raid_last_scanned", "last_scanned"),
    )


class Stop(Base):
    __tablename__ = "pokestop"

    pokestop_id = Column(
        String(length=50, collation="utf8mb4_unicode_ci"), primary_key=True
    )
    enabled = Column(TINYINT, default=1, nullable=False)
    latitude = Column(DOUBLE(asdecimal=False), nullable=False)
    longitude = Column(DOUBLE(asdecimal=False), nullable=False)
    last_modified = Column(DateTime, default=datetime.utcnow())
    lure_expiration = Column(DateTime)
    active_fort_modifier = Column(SmallInteger)
    last_updated = Column(DateTime)
    name = Column(String(length=250, collation="utf8mb4_unicode_ci"))
    image = Column(String(length=255, collation="utf8mb4_unicode_ci"))
    incident_start = Column(DateTime)
    incident_expiration = Column(DateTime)
    incident_grunt_type = Column(SmallInteger)

    __table_args__ = (
        Index("pokestop_last_modified", "last_modified"),
        Index("pokestop_lure_expiration", "lure_expiration"),
        Index("pokestop_active_fort_modifier", "active_fort_modifier"),
        Index("pokestop_last_updated", "last_updated"),
        Index("pokestop_latitude_longitude", "latitude", "longitude"),
    )


class Quest(Base):
    __tablename__ = "trs_quest"

    GUID = Column(String(length=50, collation="utf8mb4_unicode_ci"), primary_key=True)
    quest_type = Column(TINYINT, nullable=False)
    quest_timestamp = Column(Integer, nullable=False)
    quest_stardust = Column(SmallInteger, nullable=False)
    quest_pokemon_id = Column(SmallInteger, nullable=False)
    quest_reward_type = Column(SmallInteger, nullable=False)
    quest_item_id = Column(SmallInteger, nullable=False)
    quest_item_amount = Column(TINYINT, nullable=False)
    quest_target = Column(TINYINT, nullable=False)
    quest_condition = Column(String(length=500, collation="utf8mb4_unicode_ci"))
    quest_reward = Column(String(length=1000, collation="utf8mb4_unicode_ci"))
    quest_template = Column(String(length=100, collation="utf8mb4_unicode_ci"))
    quest_task = Column(String(length=150, collation="utf8mb4_unicode_ci"))
    quest_pokemon_form_id = Column(SmallInteger, default=0, nullable=False)
    quest_pokemon_costume_id = Column(SmallInteger, default=0, nullable=False)

    __table_args__ = (Index("quest_type", "quest_type"),)


class Weather(Base):
    __tablename__ = "weather"

    s2_cell_id = Column(
        String(length=50, collation="utf8mb4_unicode_ci"), primary_key=True
    )
    latitude = Column(DOUBLE(asdecimal=False), nullable=False)
    longitude = Column(DOUBLE(asdecimal=False), nullable=False)
    cloud_level = Column(SmallInteger)
    rain_level = Column(SmallInteger)
    wind_level = Column(SmallInteger)
    snow_level = Column(SmallInteger)
    fog_level = Column(SmallInteger)
    wind_direction = Column(SmallInteger)
    gameplay_weather = Column(SmallInteger)
    severity = Column(SmallInteger)
    warn_weather = Column(SmallInteger)
    world_time = Column(SmallInteger)
    last_updated = Column(DateTime)

    __table_args__ = (Index("weather_last_updated", "last_updated"),)


class Spawnpoint(Base):
    __tablename__ = "trs_spawn"

    spawnpoint = Column(BIGINT(unsigned=True), primary_key=True)
    latitude = Column(DOUBLE(asdecimal=False), nullable=False)
    longitude = Column(DOUBLE(asdecimal=False), nullable=False)
    spawndef = Column(Integer, default=240, nullable=False)
    earliest_unseen = Column(Integer, nullable=False)
    last_scanned = Column(DateTime)
    first_detection = Column(DateTime, default=datetime.utcnow(), nullable=False)
    last_non_scanned = Column(DateTime)
    calc_endminsec = Column(String(length=5, collation="utf8mb4_unicode_ci"))
    eventid = Column(Integer, default=1, nullable=False)

    __table_args__ = (Index("event_lat_long", "eventid", "latitude", "longitude"),)


class ScannedLocation(Base):
    __tablename__ = "scannedlocation"

    cellid = Column(BIGINT(unsigned=True), primary_key=True)
    latitude = Column(DOUBLE(asdecimal=False), nullable=False)
    longitude = Column(DOUBLE(asdecimal=False), nullable=False)
    last_modified = Column(DateTime)

    __table_args__ = (
        Index("scannedlocation_last_modified", "last_modified"),
        Index("scannedlocation_latitude_longitude", "latitude", "longitude"),
    )


class S2Cell(Base):
    __tablename__ = "trs_s2cells"

    id = Column(BIGINT(unsigned=True), primary_key=True)
    center_latitude = Column(DOUBLE(asdecimal=False), nullable=False)
    center_longitude = Column(DOUBLE(asdecimal=False), nullable=False)
    updated = Column(Integer, nullable=False)

    __table_args__ = (
        Index("s2cells_id", "id"),
        Index("s2cells_updated", "updated"),
        Index("s2cells_latitude_longitude", "center_latitude", "center_longitude"),
    )
