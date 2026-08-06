# ============================================================
# Database Models for NanoBio Studio
# Using SQLAlchemy for ORM-based persistence
# ============================================================

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json
from pathlib import Path

# Database setup
DB_URL = "sqlite:///nanobio_studio.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============================================================
# Database Models
# ============================================================

class User(Base):
    """User model for storing user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    designs = relationship("Design", back_populates="creator", cascade="all, delete-orphan")


class Project(Base):
    """Project model for grouping designs"""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", back_populates="projects")
    designs = relationship("Design", back_populates="project", cascade="all, delete-orphan")


class Design(Base):
    """Design model for storing nanoparticle designs"""
    __tablename__ = "designs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    
    # Design parameters stored as JSON
    parameters = Column(JSON, nullable=False)
    
    # Design metrics (denormalized for quick access)
    delivery_score = Column(Float, nullable=True)
    toxicity_score = Column(Float, nullable=True)
    cost_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_favorited = Column(Integer, default=0)  # Boolean stored as int
    version = Column(Integer, default=1)
    
    # Relationships
    creator = relationship("User", back_populates="designs")
    project = relationship("Project", back_populates="designs")
    optimizations = relationship("Optimization", back_populates="design", cascade="all, delete-orphan")
    simulations = relationship("Simulation", back_populates="design", cascade="all, delete-orphan")


class Optimization(Base):
    """Optimization run model for tracking optimization history"""
    __tablename__ = "optimizations"
    
    id = Column(Integer, primary_key=True, index=True)
    design_id = Column(Integer, ForeignKey("designs.id"), nullable=False)
    
    # Optimization configuration
    objective_weights = Column(JSON, nullable=False)  # {"efficacy": 0.5, "safety": 0.3, "cost": 0.2}
    algorithm = Column(String, default="optuna")  # optuna, genetic, grid_search, etc.
    
    # Results
    pareto_front = Column(JSON, nullable=True)  # List of optimal designs
    best_design = Column(JSON, nullable=True)
    optimization_history = Column(JSON, nullable=True)  # Convergence info
    
    # Metadata
    status = Column(String, default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total_evaluations = Column(Integer, default=0)
    
    # Relationships
    design = relationship("Design", back_populates="optimizations")


class Simulation(Base):
    """Simulation model for storing simulation results"""
    __tablename__ = "simulations"
    
    id = Column(Integer, primary_key=True, index=True)
    design_id = Column(Integer, ForeignKey("designs.id"), nullable=False)
    
    # Simulation parameters
    simulation_type = Column(String)  # "delivery", "toxicity", "stability", etc.
    parameters = Column(JSON, nullable=False)
    
    # Results
    results = Column(JSON, nullable=False)
    execution_time = Column(Float, nullable=True)
    status = Column(String, default="completed")  # pending, running, completed, failed
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    design = relationship("Design", back_populates="simulations")


# ============================================================
# Initialize Database
# ============================================================

def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Database Operations
# ============================================================

class DesignRepository:
    """Repository for design database operations"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def create_design(self, user_id: int, name: str, parameters: dict, 
                     project_id: int = None, description: str = None) -> Design:
        """Create a new design"""
        design = Design(
            user_id=user_id,
            project_id=project_id,
            name=name,
            description=description,
            parameters=parameters
        )
        self.db.add(design)
        self.db.commit()
        self.db.refresh(design)
        return design
    
    def get_design(self, design_id: int) -> Design:
        """Get a design by ID"""
        return self.db.query(Design).filter(Design.id == design_id).first()
    
    def list_user_designs(self, user_id: int, project_id: int = None) -> list:
        """List all designs for a user, optionally filtered by project"""
        query = self.db.query(Design).filter(Design.user_id == user_id)
        if project_id:
            query = query.filter(Design.project_id == project_id)
        return query.order_by(Design.created_at.desc()).all()
    
    def update_design(self, design_id: int, **kwargs) -> Design:
        """Update a design"""
        design = self.get_design(design_id)
        if design:
            for key, value in kwargs.items():
                if hasattr(design, key):
                    setattr(design, key, value)
            design.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(design)
        return design
    
    def update_design_scores(self, design_id: int, delivery: float, 
                            toxicity: float, cost: float) -> Design:
        """Update design scores and calculate overall score"""
        design = self.get_design(design_id)
        if design:
            design.delivery_score = delivery
            design.toxicity_score = toxicity
            design.cost_score = cost
            # Simple overall score (can be weighted)
            design.overall_score = (delivery * 0.4 + (10 - toxicity) * 0.3 + (100 - cost) * 0.3) / 100
            design.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(design)
        return design
    
    def delete_design(self, design_id: int) -> bool:
        """Delete a design"""
        design = self.get_design(design_id)
        if design:
            self.db.delete(design)
            self.db.commit()
            return True
        return False
    
    def favorite_design(self, design_id: int, is_favorite: bool) -> Design:
        """Mark a design as favorite"""
        return self.update_design(design_id, is_favorited=1 if is_favorite else 0)


class ProjectRepository:
    """Repository for project database operations"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def create_project(self, user_id: int, name: str, description: str = None) -> Project:
        """Create a new project"""
        project = Project(
            user_id=user_id,
            name=name,
            description=description
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project
    
    def list_user_projects(self, user_id: int) -> list:
        """List all projects for a user"""
        return self.db.query(Project).filter(Project.user_id == user_id).order_by(Project.created_at.desc()).all()
    
    def get_project(self, project_id: int) -> Project:
        """Get a project by ID"""
        return self.db.query(Project).filter(Project.id == project_id).first()
    
    def update_project(self, project_id: int, **kwargs) -> Project:
        """Update a project"""
        project = self.get_project(project_id)
        if project:
            for key, value in kwargs.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            project.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(project)
        return project
    
    def delete_project(self, project_id: int) -> bool:
        """Delete a project (and all its designs)"""
        project = self.get_project(project_id)
        if project:
            self.db.delete(project)
            self.db.commit()
            return True
        return False


class OptimizationRepository:
    """Repository for optimization database operations"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def create_optimization(self, design_id: int, objective_weights: dict, 
                           algorithm: str = "optuna") -> Optimization:
        """Create a new optimization run"""
        opt = Optimization(
            design_id=design_id,
            objective_weights=objective_weights,
            algorithm=algorithm,
            status="pending"
        )
        self.db.add(opt)
        self.db.commit()
        self.db.refresh(opt)
        return opt
    
    def get_optimization(self, optimization_id: int) -> Optimization:
        """Get optimization by ID"""
        return self.db.query(Optimization).filter(Optimization.id == optimization_id).first()
    
    def update_optimization(self, optimization_id: int, **kwargs) -> Optimization:
        """Update optimization"""
        opt = self.get_optimization(optimization_id)
        if opt:
            for key, value in kwargs.items():
                if hasattr(opt, key):
                    setattr(opt, key, value)
            self.db.commit()
            self.db.refresh(opt)
        return opt
    
    def list_design_optimizations(self, design_id: int) -> list:
        """List all optimizations for a design"""
        return self.db.query(Optimization).filter(
            Optimization.design_id == design_id
        ).order_by(Optimization.created_at.desc()).all()


# Initialize database on import
init_db()
