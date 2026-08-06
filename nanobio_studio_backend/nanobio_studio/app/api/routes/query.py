"""
Query and summary routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from nanobio_studio.app.api.deps import get_db
from nanobio_studio.app.db.models import (
    Lipid, Payload, Formulation, Characterization, Assay, Experiment, BiologicalModel
)
from nanobio_studio.app.schemas.lipids import LipidResponse
from nanobio_studio.app.schemas.formulations import FormulationResponse
from nanobio_studio.app.core.logging import get_logger

router = APIRouter(prefix="/query", tags=["query"])
log = get_logger("query.routes")


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)) -> dict:
    """Get database summary statistics."""
    try:
        # Count records
        lipid_count = (await db.execute(select(func.count(Lipid.lipid_id)))).scalar()
        payload_count = (await db.execute(select(func.count(Payload.payload_id)))).scalar()
        formulation_count = (await db.execute(select(func.count(Formulation.id)))).scalar()
        experiment_count = (await db.execute(select(func.count(Experiment.id)))).scalar()
        assay_count = (await db.execute(select(func.count(Assay.id)))).scalar()
        
        # Average characterization
        avg_size = (await db.execute(select(func.avg(Characterization.particle_size_nm)))).scalar()
        avg_pdi = (await db.execute(select(func.avg(Characterization.pdi)))).scalar()
        
        return {
            "lipids": lipid_count or 0,
            "payloads": payload_count or 0,
            "formulations": formulation_count or 0,
            "experiments": experiment_count or 0,
            "assays": assay_count or 0,
            "average_particle_size_nm": float(avg_size) if avg_size else None,
            "average_pdi": float(avg_pdi) if avg_pdi else None,
        }
    except Exception as e:
        log.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lipids")
async def list_lipids(db: AsyncSession = Depends(get_db)) -> dict:
    """Get all lipids."""
    try:
        result = await db.execute(select(Lipid))
        lipids = result.scalars().all()
        
        return {
            "count": len(lipids),
            "lipids": [
                {
                    "lipid_id": l.lipid_id,
                    "lipid_name": l.lipid_name,
                    "lipid_class": l.lipid_class,
                    "molecular_weight": l.molecular_weight,
                }
                for l in lipids
            ]
        }
    except Exception as e:
        log.error(f"Error listing lipids: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formulations")
async def list_formulations(db: AsyncSession = Depends(get_db)) -> dict:
    """Get all formulations."""
    try:
        result = await db.execute(select(Formulation))
        formulations = result.scalars().all()
        
        return {
            "count": len(formulations),
            "formulations": [
                {
                    "id": f.id,
                    "formulation_id": f.formulation_id,
                    "intended_target": f.intended_target,
                    "payload_id": f.payload_id,
                    "ionizable_ratio": f.ionizable_ratio,
                }
                for f in formulations
            ]
        }
    except Exception as e:
        log.error(f"Error listing formulations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formulation/{formulation_id}")
async def get_formulation_detail(formulation_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Get detailed formulation information."""
    try:
        result = await db.execute(select(Formulation).filter(Formulation.id == formulation_id))
        formulation = result.scalar_one_or_none()
        
        if not formulation:
            raise HTTPException(status_code=404, detail="Formulation not found")
        
        return {
            "id": formulation.id,
            "formulation_id": formulation.formulation_id,
            "intended_target": formulation.intended_target,
            "ligand": formulation.ligand_name,
            "ratios": {
                "ionizable": formulation.ionizable_ratio,
                "helper": formulation.helper_ratio,
                "sterol": formulation.sterol_ratio,
                "peg": formulation.peg_ratio,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting formulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
