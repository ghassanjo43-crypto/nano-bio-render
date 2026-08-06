"""
Data exporters for ML-ready datasets

Export training dataframes to various formats (Parquet, CSV)
"""

from typing import Optional
from pathlib import Path
import pandas as pd
from loguru import logger

logger = logger.bind(module="ml.exporters")


class ParquetExporter:
    """Export dataframes to Parquet format (columnar, compressed)"""
    
    def __init__(self, compress: str = "snappy"):
        """
        Initialize Parquet exporter
        
        Args:
            compress: Compression method ('snappy', 'gzip', 'brotli', or None)
        """
        self.logger = logger
        self.compress = compress
    
    def export(self, df: pd.DataFrame, filepath: str) -> None:
        """
        Export dataframe to Parquet
        
        Args:
            df: Pandas DataFrame to export
            filepath: Output file path
        """
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(filepath, compression=self.compress, index=False)
            self.logger.info(f"Exported {len(df)} rows to {filepath}")
        except Exception as e:
            self.logger.error(f"Error exporting to Parquet: {e}")
            raise
    
    def read(self, filepath: str) -> pd.DataFrame:
        """
        Read Parquet file
        
        Args:
            filepath: Path to Parquet file
            
        Returns:
            Loaded DataFrame
        """
        try:
            df = pd.read_parquet(filepath)
            self.logger.info(f"Loaded {len(df)} rows from {filepath}")
            return df
        except Exception as e:
            self.logger.error(f"Error reading Parquet: {e}")
            raise


class CSVExporter:
    """Export dataframes to CSV format (human-readable)"""
    
    def __init__(self):
        """Initialize CSV exporter"""
        self.logger = logger
    
    def export(self, df: pd.DataFrame, filepath: str, include_index: bool = False) -> None:
        """
        Export dataframe to CSV
        
        Args:
            df: Pandas DataFrame to export
            filepath: Output file path
            include_index: Whether to include row indices
        """
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(filepath, index=include_index)
            self.logger.info(f"Exported {len(df)} rows to {filepath}")
        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            raise
    
    def read(self, filepath: str) -> pd.DataFrame:
        """
        Read CSV file
        
        Args:
            filepath: Path to CSV file
            
        Returns:
            Loaded DataFrame
        """
        try:
            df = pd.read_csv(filepath)
            self.logger.info(f"Loaded {len(df)} rows from {filepath}")
            return df
        except Exception as e:
            self.logger.error(f"Error reading CSV: {e}")
            raise


class DatasetExporter:
    """Combined exporter for both Parquet and CSV formats"""
    
    def __init__(self):
        """Initialize combined exporter"""
        self.logger = logger
        self.parquet_exporter = ParquetExporter()
        self.csv_exporter = CSVExporter()
    
    def export_all(
        self,
        df: pd.DataFrame,
        output_dir: str,
        dataset_name: str = "dataset",
    ) -> dict:
        """
        Export dataframe in both Parquet and CSV formats
        
        Args:
            df: Dataframe to export
            output_dir: Output directory
            dataset_name: Base name for files
            
        Returns:
            Dictionary with paths to exported files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        parquet_path = output_path / f"{dataset_name}.parquet"
        csv_path = output_path / f"{dataset_name}.csv"
        
        # Export to both formats
        self.parquet_exporter.export(df, str(parquet_path))
        self.csv_exporter.export(df, str(csv_path))
        
        self.logger.info(f"Exported dataset to {output_dir}")
        
        return {
            "parquet": str(parquet_path),
            "csv": str(csv_path),
            "rows": len(df),
            "columns": len(df.columns),
        }
    
    def export_train_test(
        self,
        df_train: pd.DataFrame,
        df_test: pd.DataFrame,
        output_dir: str,
        prefix: str = "dataset",
    ) -> dict:
        """
        Export train/test split datasets
        
        Args:
            df_train: Training dataframe
            df_test: Test dataframe
            output_dir: Output directory
            prefix: File name prefix
            
        Returns:
            Dictionary with paths to exported files
        """
        train_result = self.export_all(df_train, output_dir, f"{prefix}_train")
        test_result = self.export_all(df_test, output_dir, f"{prefix}_test")
        
        return {
            "train": train_result,
            "test": test_result,
        }
