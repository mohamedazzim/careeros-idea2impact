"""
LangSmith dataset operations.
Create and manage datasets for evaluation.
"""
import logging
from typing import Optional, Dict, Any

from .client import get_manager

logger = logging.getLogger(__name__)


def create_dataset(name: str, description: Optional[str] = None) -> Optional[str]:
    """
    Create a dataset for evaluation.
    
    Args:
        name: Dataset name
        description: Dataset description
        
    Returns:
        Dataset ID if successful
    """
    manager = get_manager()
    
    if not manager.enabled:
        return None
    
    try:
        dataset = manager.client.create_dataset(
            dataset_name=name,
            description=description
        )
        return dataset.id
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}")
        return None


def log_to_dataset(
    dataset_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    expected_outputs: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Log an example to a dataset.
    
    Args:
        dataset_name: Name of the dataset
        inputs: Input data
        outputs: Actual outputs
        expected_outputs: Expected/correct outputs (for eval datasets)
        
    Returns:
        Example ID if successful
    """
    manager = get_manager()
    
    if not manager.enabled:
        return None
    
    try:
        example = manager.client.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_name=dataset_name,
            metadata=expected_outputs
        )
        return example.id
    except Exception as e:
        logger.error(f"Failed to log to dataset: {e}")
        return None
