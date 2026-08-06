"""
SQLAlchemy ORM models for NanoBio Studio backend.
Defines the database schema for all entities.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime, Index, func
from sqlalchemy.orm import relationship
from datetime import datetime
from nanobio_studio.app.db.base import Base, TimestampMixin


class Lipid(Base, TimestampMixin):
    """Lipid entity - ingredient for formulations."""
    
    __tablename__ = "lipids"
    __table_args__ = (
        Index("idx_lipid_name", "lipid_name"),
        Index("idx_lipid_class", "lipid_class"),
    )

    lipid_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lipid_name = Column(String(256), unique=True, nullable=False, index=True)
    lipid_class = Column(String(64), nullable=False, index=True)
    structure_smiles = Column(Text, nullable=True)
    molecular_weight = Column(Float, nullable=True)
    pka = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    formulations_ionizable = relationship(
        "Formulation",
        foreign_keys="Formulation.ionizable_lipid_id",
        back_populates="ionizable_lipid"
    )
    formulations_helper = relationship(
        "Formulation",
        foreign_keys="Formulation.helper_lipid_id",
        back_populates="helper_lipid"
    )
    formulations_sterol = relationship(
        "Formulation",
        foreign_keys="Formulation.sterol_lipid_id",
        back_populates="sterol_lipid"
    )
    formulations_peg = relationship(
        "Formulation",
        foreign_keys="Formulation.peg_lipid_id",
        back_populates="peg_lipid"
    )


class Payload(Base, TimestampMixin):
    """Payload entity - therapeutic agent to be delivered."""
    
    __tablename__ = "payloads"
    __table_args__ = (
        Index("idx_payload_type", "payload_type"),
        Index("idx_target_gene", "target_gene"),
    )

    payload_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    payload_type = Column(String(64), nullable=False, index=True)
    payload_name = Column(String(256), unique=True, nullable=False, index=True)
    sequence_or_description = Column(Text, nullable=True)
    target_gene = Column(String(256), nullable=True, index=True)
    payload_length = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    formulations = relationship("Formulation", back_populates="payload")


class Formulation(Base, TimestampMixin):
    """Formulation entity - composition of lipids and payload."""
    
    __tablename__ = "formulations"
    __table_args__ = (
        Index("idx_formulation_id", "formulation_id"),
        Index("idx_intended_target", "intended_target"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    formulation_id = Column(String(256), unique=True, nullable=True, index=True)
    
    ionizable_lipid_id = Column(Integer, ForeignKey("lipids.lipid_id"), nullable=False)
    helper_lipid_id = Column(Integer, ForeignKey("lipids.lipid_id"), nullable=False)
    sterol_lipid_id = Column(Integer, ForeignKey("lipids.lipid_id"), nullable=False)
    peg_lipid_id = Column(Integer, ForeignKey("lipids.lipid_id"), nullable=False)
    
    ionizable_ratio = Column(Float, nullable=False)
    helper_ratio = Column(Float, nullable=False)
    sterol_ratio = Column(Float, nullable=False)
    peg_ratio = Column(Float, nullable=False)
    
    ligand_name = Column(String(256), nullable=True)
    
    payload_id = Column(Integer, ForeignKey("payloads.payload_id"), nullable=False)
    intended_target = Column(String(256), nullable=True, index=True)
    formulation_version = Column(String(64), nullable=True)

    # Relationships
    ionizable_lipid = relationship(
        "Lipid",
        foreign_keys=[ionizable_lipid_id],
        back_populates="formulations_ionizable"
    )
    helper_lipid = relationship(
        "Lipid",
        foreign_keys=[helper_lipid_id],
        back_populates="formulations_helper"
    )
    sterol_lipid = relationship(
        "Lipid",
        foreign_keys=[sterol_lipid_id],
        back_populates="formulations_sterol"
    )
    peg_lipid = relationship(
        "Lipid",
        foreign_keys=[peg_lipid_id],
        back_populates="formulations_peg"
    )
    payload = relationship("Payload", back_populates="formulations")
    process_conditions = relationship("ProcessConditions", back_populates="formulation")
    characterizations = relationship("Characterization", back_populates="formulation")
    assays = relationship("Assay", back_populates="formulation")


class ProcessConditions(Base, TimestampMixin):
    """Process conditions for formulation preparation."""
    
    __tablename__ = "process_conditions"
    __table_args__ = (
        Index("idx_formulation_id", "formulation_id"),
        Index("idx_batch_id", "batch_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    formulation_id = Column(Integer, ForeignKey("formulations.id"), nullable=False)
    preparation_method = Column(String(256), nullable=False)
    flow_rate_ratio = Column(String(64), nullable=True)
    total_flow_rate_ml_min = Column(Float, nullable=True)
    buffer_type = Column(String(256), nullable=True)
    buffer_ph = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    mixing_chip_type = Column(String(256), nullable=True)
    operator_or_robot = Column(String(256), nullable=True)
    batch_id = Column(String(256), nullable=True, index=True)

    # Relationships
    formulation = relationship("Formulation", back_populates="process_conditions")
    characterizations = relationship("Characterization", back_populates="process")


class Characterization(Base, TimestampMixin):
    """Particle characterization results."""
    
    __tablename__ = "characterizations"
    __table_args__ = (
        Index("idx_formulation_id", "formulation_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    formulation_id = Column(Integer, ForeignKey("formulations.id"), nullable=False)
    process_id = Column(Integer, ForeignKey("process_conditions.id"), nullable=True)
    
    particle_size_nm = Column(Float, nullable=True)
    pdi = Column(Float, nullable=True)
    zeta_potential_mv = Column(Float, nullable=True)
    encapsulation_efficiency_pct = Column(Float, nullable=True)
    stability_hours = Column(Float, nullable=True)
    morphology = Column(String(256), nullable=True)
    measurement_method = Column(String(256), nullable=True)
    measurement_date = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    formulation = relationship("Formulation", back_populates="characterizations")
    process = relationship("ProcessConditions", back_populates="characterizations")


class BiologicalModel(Base, TimestampMixin):
    """Biological model for testing."""
    
    __tablename__ = "biological_models"
    __table_args__ = (
        Index("idx_model_name", "model_name"),
        Index("idx_model_type", "model_type"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_type = Column(String(64), nullable=False, index=True)
    model_name = Column(String(256), unique=True, nullable=False, index=True)
    species = Column(String(64), nullable=True)
    disease_context = Column(Text, nullable=True)
    receptor_profile = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    assays = relationship("Assay", back_populates="model")


class Assay(Base, TimestampMixin):
    """Assay results."""
    
    __tablename__ = "assays"
    __table_args__ = (
        Index("idx_formulation_id", "formulation_id"),
        Index("idx_model_id", "model_id"),
        Index("idx_assay_type", "assay_type"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    formulation_id = Column(Integer, ForeignKey("formulations.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("biological_models.id"), nullable=False)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True)
    
    assay_type = Column(String(64), nullable=False, index=True)
    dose = Column(Float, nullable=True)
    route_of_administration = Column(String(128), nullable=True)
    timepoint_hours = Column(Float, nullable=True)
    result_value = Column(Float, nullable=True)
    result_unit = Column(String(128), nullable=True)
    normalized_score = Column(Float, nullable=True)
    outcome_label = Column(String(256), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    formulation = relationship("Formulation", back_populates="assays")
    model = relationship("BiologicalModel", back_populates="assays")
    experiment = relationship("Experiment", back_populates="assays")


class Experiment(Base, TimestampMixin):
    """Experiment metadata."""
    
    __tablename__ = "experiments"
    __table_args__ = (
        Index("idx_experiment_id", "experiment_id"),
        Index("idx_source_type", "source_type"),
        Index("idx_qc_status", "qc_status"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    experiment_id = Column(String(256), unique=True, nullable=True, index=True)
    experiment_name = Column(String(512), nullable=False)
    source_type = Column(String(64), nullable=False, index=True)
    source_reference = Column(Text, nullable=True)
    date_run = Column(DateTime(timezone=True), nullable=True)
    scientist = Column(String(256), nullable=True)
    institution = Column(String(512), nullable=True)
    qc_status = Column(String(64), nullable=False, index=True, default="pending")
    comments = Column(Text, nullable=True)

    # Relationships
    assays = relationship("Assay", back_populates="experiment")
