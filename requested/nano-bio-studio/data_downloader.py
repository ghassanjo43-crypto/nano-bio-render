#!/usr/bin/env python3
"""
External Data Downloader Utility
Downloads and integrates external scientific datasets into NanoBio Studio
Supports: ToxCast, FDA FAERS, GEO, ChemSpider, ClinicalTrials, PDB
"""

import sys
from pathlib import Path
import logging
sys.path.insert(0, str(Path(__file__).parent))

from modules.data_integrations import DataIntegrationOrchestrator, save_external_dataset

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def download_all_external_datasets(output_dir: str = "data/external") -> dict:
    """
    Download and integrate all external scientific datasets
    
    This function integrates datasets from:
    - EPA ToxCast (10M+ toxicity data points)
    - FDA FAERS (20M+ adverse events)
    - NCBI GEO (100K+ gene expression experiments)
    - ChemSpider (50M+ lipid components)
    - ClinicalTrials.gov (200+ LNP trials)
    - PDB (200K+ 3D structures)
    
    Args:
        output_dir: Directory to save datasets
        
    Returns:
        Dictionary with paths to all downloaded datasets
    """
    logger.info("\n" + "🌍 "*20)
    logger.info("NANOBIO STUDIO - EXTERNAL DATA INTEGRATION")
    logger.info("🌍 "*20 + "\n")
    
    orchestrator = DataIntegrationOrchestrator()
    
    # Integrate all datasets
    datasets_created = {
        "toxcast": orchestrator.integrate_toxcast(),
        "faers": orchestrator.integrate_faers(),
        "geo": orchestrator.integrate_geo(),
        "chemspider": orchestrator.integrate_chemspider(),
        "clinical_trials": orchestrator.integrate_clinical_trials(),
        "pdb": orchestrator.integrate_pdb(),
    }
    
    # Save all datasets
    saved_paths = {}
    for name, df in datasets_created.items():
        if df is not None and len(df) > 0:
            path = save_external_dataset(df, name, output_dir)
            saved_paths[name] = path
    
    # Get combined dataset
    combined_df = orchestrator.integrate_all()
    if len(combined_df) > 0:
        combined_path = save_external_dataset(combined_df, "all_external_sources", output_dir)
        saved_paths["combined"] = combined_path
    
    # Print summary
    print(orchestrator.get_integration_summary())
    
    print("\n📂 SAVED DATASETS:")
    for source, path in saved_paths.items():
        print(f"  ✓ {source:20} → {path}")
    
    return saved_paths


def download_single_dataset(source: str, output_dir: str = "data/external") -> str:
    """
    Download a single external dataset
    
    Args:
        source: Name of source ('toxcast', 'faers', 'geo', 'chemspider', 'clinical_trials', 'pdb')
        output_dir: Directory to save dataset
        
    Returns:
        Path to saved dataset
    """
    orchestrator = DataIntegrationOrchestrator()
    
    sources = {
        "toxcast": orchestrator.integrate_toxcast,
        "faers": orchestrator.integrate_faers,
        "geo": orchestrator.integrate_geo,
        "chemspider": orchestrator.integrate_chemspider,
        "clinical_trials": orchestrator.integrate_clinical_trials,
        "pdb": orchestrator.integrate_pdb,
    }
    
    if source not in sources:
        logger.error(f"✗ Unknown source: {source}")
        logger.info(f"Available sources: {', '.join(sources.keys())}")
        return ""
    
    logger.info(f"\n📥 Downloading {source.upper()} dataset...\n")
    df = sources[source]()
    
    if df is not None and len(df) > 0:
        path = save_external_dataset(df, source, output_dir)
        logger.info(f"✓ Dataset saved: {path}")
        return path
    else:
        logger.error(f"✗ Failed to download {source}")
        return ""


def get_dataset_info() -> dict:
    """Get information about all available external datasets"""
    return {
        "toxcast": {
            "name": "EPA ToxCast",
            "records": "100+ (template)",
            "data_points": "10M+ (live API)",
            "description": "Toxicity screening assay data for 12K+ chemicals",
            "url": "https://www.epa.gov/comptox/comptox-chemicals-dashboard",
            "access": "Free",
            "ml_value": "🔴🔴🔴 (High)"
        },
        "faers": {
            "name": "FDA FAERS",
            "records": "500 (template)",
            "data_points": "20M+ (live)",
            "description": "FDA adverse events reporting system - post-market safety",
            "url": "https://fis.fda.gov/extensions/FPD-QDE-FAERS/",
            "access": "Free",
            "ml_value": "🔴🔴🔴 (High)"
        },
        "geo": {
            "name": "NCBI GEO",
            "records": "300 (template)",
            "data_points": "100K+ (live)",
            "description": "Gene Expression Omnibus - immune response after LNP exposure",
            "url": "https://www.ncbi.nlm.nih.gov/geo/",
            "access": "Free",
            "ml_value": "🔴🔴🔴 (High)"
        },
        "chemspider": {
            "name": "ChemSpider",
            "records": "300 (template)",
            "data_points": "50M+ (live)",
            "description": "Chemical structure database - lipid component properties",
            "url": "https://www.chemspider.com/",
            "access": "Free (with registration)",
            "ml_value": "🔴🔴 (Medium-High)"
        },
        "clinical_trials": {
            "name": "ClinicalTrials.gov",
            "records": "250 (template)",
            "data_points": "200+ LNP trials",
            "description": "Clinical trial data - real-world LNP efficacy and safety",
            "url": "https://clinicaltrials.gov/",
            "access": "Free API",
            "ml_value": "🔴🔴🔴 (Very High)"
        },
        "pdb": {
            "name": "PDB",
            "records": "200 (template)",
            "data_points": "200K+ structures",
            "description": "3D protein structures - lipid and nanoparticle geometry",
            "url": "https://www.rcsb.org/",
            "access": "Free",
            "ml_value": "🟠🟠 (Medium)"
        }
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="NanoBio Studio External Data Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all datasets
  python data_downloader.py --all
  
  # Download specific dataset
  python data_downloader.py --source toxcast
  
  # List available sources
  python data_downloader.py --list
        """
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all external datasets"
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["toxcast", "faers", "geo", "chemspider", "clinical_trials", "pdb"],
        help="Download specific dataset source"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/external",
        help="Output directory for datasets (default: data/external)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available data sources"
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\n" + "="*80)
        print("AVAILABLE EXTERNAL DATA SOURCES FOR NANOBIO STUDIO")
        print("="*80 + "\n")
        
        info = get_dataset_info()
        for source_id, details in info.items():
            print(f"📊 {details['name']} ({source_id})")
            print(f"   Records: {details['records']} | Data Points: {details['data_points']}")
            print(f"   Description: {details['description']}")
            print(f"   URL: {details['url']}")
            print(f"   Access: {details['access']} | ML Value: {details['ml_value']}")
            print()
        
        print("="*80)
        print("Download command: python data_downloader.py --source <name> OR --all")
        print("="*80 + "\n")
    
    elif args.all:
        saved_paths = download_all_external_datasets(args.output)
        print(f"\n✅ Downloaded {len(saved_paths)} datasets!")
        
    elif args.source:
        path = download_single_dataset(args.source, args.output)
        if path:
            print(f"\n✅ Successfully downloaded {args.source} dataset!")
            print(f"   Saved to: {path}")
    
    else:
        parser.print_help()
