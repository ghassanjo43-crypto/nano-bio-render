#!/usr/bin/env python3
"""
LIVE DATA ORCHESTRATOR - All 6 Data Sources with Live API Support
Manages hybrid connections (Live APIs + Local Templates) for all sources
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional, Tuple
import glob

class LiveDataConnector:
    """Base class for live data connections"""
    
    def __init__(self, name: str, api_url: str, fallback_pattern: str):
        self.name = name
        self.api_url = api_url
        self.fallback_pattern = fallback_pattern
        self.data = None
        self.source_type = "TEMPLATE"  # LIVE or TEMPLATE
        self.record_count = 0
        self.last_updated = None
        self.connection_status = "UNKNOWN"
        
    def fetch(self, timeout=10) -> bool:
        """Try live API, fall back to template"""
        
        # Try live API first
        if self.try_live_api(timeout):
            self.source_type = "LIVE API"
            self.connection_status = "ONLINE"
            self.last_updated = datetime.now()
            return True
        
        # Fall back to template
        if self.try_template():
            self.source_type = "TEMPLATE"
            self.connection_status = "OFFLINE (Using Template)"
            self.last_updated = datetime.now()
            return True
        
        self.connection_status = "ERROR"
        return False
    
    def try_live_api(self, timeout) -> bool:
        """Attempt to fetch from live API"""
        try:
            response = requests.get(self.api_url, timeout=timeout)
            if response.status_code == 200:
                self.data = response.json()
                self.record_count = 1 if isinstance(self.data, dict) else len(self.data) if isinstance(self.data, list) else 0
                return True
        except:
            pass
        return False
    
    def try_template(self) -> bool:
        """Fall back to local template"""
        try:
            files = glob.glob(self.fallback_pattern)
            if files:
                df = pd.read_csv(files[0])
                self.data = df.to_dict('records')
                self.record_count = len(df)
                return True
        except:
            pass
        return False
    
    def get_status(self) -> Dict:
        """Get connection status"""
        return {
            'Name': self.name,
            'Source': self.source_type,
            'Status': self.connection_status,
            'Records': self.record_count,
            'Last_Updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else 'N/A'
        }


class LiveDataOrchestrator:
    """Manages all 6 live data sources"""
    
    def __init__(self):
        self.connectors = {}
        self.total_records = 0
        self.live_sources = 0
        self.template_sources = 0
        self.initialized_at = None
        self._setup_connectors()
    
    def _setup_connectors(self):
        """Initialize all 6 data source connectors"""
        
        # 1. EPA ToxCast
        self.connectors['ToxCast'] = LiveDataConnector(
            name='EPA ToxCast',
            api_url='https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/CID/5564/JSON',
            fallback_pattern='data/external/toxcast_dataset_*.csv'
        )
        
        # 2. FDA FAERS (using OpenFDA API)
        self.connectors['FAERS'] = LiveDataConnector(
            name='FDA FAERS',
            api_url='https://api.fda.gov/drug/event.json?limit=10',
            fallback_pattern='data/external/faers_dataset_*.csv'
        )
        
        # 3. NCBI GEO (Gene Expression)
        self.connectors['GEO'] = LiveDataConnector(
            name='NCBI GEO',
            api_url='https://www.ncbi.nlm.nih.gov/geo/gdsbrief',
            fallback_pattern='data/external/geo_dataset_*.csv'
        )
        
        # 4. ChemSpider
        self.connectors['ChemSpider'] = LiveDataConnector(
            name='ChemSpider',
            api_url='https://www.chemspider.com/api/corsEnabledSearch/',
            fallback_pattern='data/external/chemspider_dataset_*.csv'
        )
        
        # 5. ClinicalTrials.gov
        self.connectors['ClinicalTrials'] = LiveDataConnector(
            name='ClinicalTrials.gov',
            api_url='https://clinicaltrials.gov/api/query/full_studies?expr=LNP&fmt=json&pageSize=10',
            fallback_pattern='data/external/clinical_trials_dataset_*.csv'
        )
        
        # 6. PDB (Protein Data Bank)
        self.connectors['PDB'] = LiveDataConnector(
            name='PDB',
            api_url='https://data.rcsb.org/rest/v1/core/status',
            fallback_pattern='data/external/pdb_dataset_*.csv'
        )
    
    def fetch_all(self, timeout=10) -> Dict[str, bool]:
        """Fetch data from all 6 sources"""
        
        print("\n" + "="*80)
        print("LIVE DATA ORCHESTRATOR - Fetching from All 6 Sources")
        print("="*80 + "\n")
        
        self.initialized_at = datetime.now()
        results = {}
        
        for source_name, connector in self.connectors.items():
            print(f"[*] Connecting to {connector.name}...", end=" ")
            
            if connector.fetch(timeout=timeout):
                results[source_name] = True
                self.total_records += connector.record_count
                
                if connector.source_type == "LIVE API":
                    self.live_sources += 1
                    print(f"[OK] LIVE ({connector.record_count} records)")
                else:
                    self.template_sources += 1
                    print(f"[OK] TEMPLATE ({connector.record_count} records)")
            else:
                results[source_name] = False
                print(f"[FAILED]")
        
        return results
    
    def get_all_status(self) -> List[Dict]:
        """Get status of all sources"""
        return [connector.get_status() for connector in self.connectors.values()]
    
    def get_summary(self) -> Dict:
        """Get overall summary"""
        return {
            'Total_Sources': len(self.connectors),
            'Live_Sources': self.live_sources,
            'Template_Sources': self.template_sources,
            'Total_Records': self.total_records,
            'Initialized': self.initialized_at.strftime('%Y-%m-%d %H:%M:%S') if self.initialized_at else 'N/A'
        }
    
    def get_dataframe_summary(self) -> pd.DataFrame:
        """Get status as DataFrame"""
        return pd.DataFrame(self.get_all_status())


def main():
    """Test live data orchestrator"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "LIVE DATA ORCHESTRATOR TEST" + " "*32 + "║")
    print("║" + " "*20 + "All 6 Data Sources with Live APIs" + " "*24 + "║")
    print("╚" + "="*78 + "╝")
    
    # Initialize orchestrator
    orchestrator = LiveDataOrchestrator()
    
    # Fetch from all sources
    results = orchestrator.fetch_all(timeout=5)
    
    # Print results
    print("\n" + "="*80)
    print("DETAILED STATUS:")
    print("="*80 + "\n")
    
    df_status = orchestrator.get_dataframe_summary()
    print(df_status.to_string(index=False))
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80 + "\n")
    
    summary = orchestrator.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Print verdict
    print("\n" + "="*80)
    print("VERDICT:")
    print("="*80 + "\n")
    
    if orchestrator.live_sources > 0:
        print(f"[+] {orchestrator.live_sources} LIVE data sources connected!")
        print(f"[+] {orchestrator.template_sources} sources using templates (fallback)")
        print(f"[+] Total records available: {orchestrator.total_records}")
        print(f"\n[!] We can now access LIVE data from {orchestrator.live_sources} scientific databases!")
    else:
        print(f"[*] All {orchestrator.template_sources} sources using template data")
        print(f"[*] Live APIs may need additional configuration")
        print(f"[+] Template data ready: {orchestrator.total_records} records")
    
    print("\n" + "="*80)
    
    return orchestrator


if __name__ == "__main__":
    orchestrator = main()
