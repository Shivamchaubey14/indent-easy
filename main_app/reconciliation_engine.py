"""
PRODUCT MAPPING RECONCILIATION ENGINE
=====================================
Enterprise-grade Excel ingestion and reconciliation system for cross-system
Product Mapping management.

Features:
- Idempotent reconciliation operations
- Zero unintended duplication
- Deterministic updates
- Full auditability
- Chunked DataFrame processing
- Atomic transactions with rollback
- Comprehensive validation and error handling
- Horizontal scalability
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import re
import hashlib
import unicodedata
from io import BytesIO
import uuid
from decimal import Decimal
import logging

from django.db import transaction, IntegrityError, models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import (
    ProductMapping, ProductMappingGroup, ProductMappingRelation,
    UploadBatch, ProcessingErrorLog, ProductMappingUpload, ReconciliationAuditLog
)

# Configure logging
logger = logging.getLogger(__name__)


class ProcessingPhase(Enum):
    """Processing phases for progress tracking"""
    FILE_LOADING = "file_loading"
    VALIDATION = "validation"
    NORMALIZATION = "normalization"
    RECONCILIATION = "reconciliation"
    PERSISTENCE = "persistence"
    FINALIZATION = "finalization"


class ValidationRule(Enum):
    """Validation rules for product mapping data"""
    GROUP_NAME_REQUIRED = "group_name_required"
    PRODUCT_NAME_REQUIRED = "product_name_required"
    PRODUCT_CODE_FORMAT = "product_code_format"
    PRODUCT_NAME_FORMAT = "product_name_format"
    NO_CODE_IN_NAME = "no_code_in_name"
    NO_NAME_IN_CODE = "no_name_in_code"
    UNIQUE_MAPPING_PER_SYSTEM = "unique_mapping_per_system"
    VALID_SYSTEM = "valid_system"
    VALID_UOM = "valid_uom"
    PRIMARY_SYSTEM_VALIDATION = "primary_system_validation"
    CONFLICTING_MAPPINGS = "conflicting_mappings"


class ReconciliationAction(Enum):
    """Actions taken during reconciliation"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    MERGE = "MERGE"
    SKIP = "SKIP"
    REJECT = "REJECT"
    DELETE = "DELETE"
    RELATE = "RELATE"


@dataclass
class ValidationError:
    """Structured validation error"""
    row_index: int
    field: str
    value: str
    rule: ValidationRule
    error_message: str
    suggestion: str = ""
    is_critical: bool = True


@dataclass
class ReconciliationResult:
    """Result of reconciliation operation"""
    row_index: int
    action: ReconciliationAction
    entity_type: str
    entity_id: Optional[int]
    entity_identifier: str
    changes: Dict[str, Any]
    mapping_actions: List[Dict] = None
    errors: List[ValidationError] = None
    
    def __post_init__(self):
        if self.mapping_actions is None:
            self.mapping_actions = []
        if self.errors is None:
            self.errors = []


@dataclass
class ProcessingMetrics:
    """Metrics for processing operations"""
    total_rows: int = 0
    rows_processed: int = 0
    rows_validated: int = 0
    rows_rejected: int = 0
    rows_skipped: int = 0
    groups_created: int = 0
    groups_updated: int = 0
    mappings_created: int = 0
    mappings_updated: int = 0
    relations_created: int = 0
    relations_updated: int = 0
    duplicates_resolved: int = 0
    merges_performed: int = 0
    processing_time_ms: int = 0
    memory_usage_mb: float = 0.0


class DataNormalizer:
    """Normalizes input data for consistent processing"""
    
    @staticmethod
    def normalize_string(value: Any) -> Optional[str]:
        """Normalize string value"""
        if value is None or pd.isna(value):
            return None
        
        # Convert to string and strip
        str_value = str(value).strip()
        if not str_value:
            return None
        
        # Normalize Unicode characters
        str_value = unicodedata.normalize('NFKC', str_value)
        
        # Remove extra whitespace
        str_value = re.sub(r'\s+', ' ', str_value)
        
        return str_value
    
    @staticmethod
    def normalize_group_name(value: Any) -> Optional[str]:
        """Special normalization for group names"""
        normalized = DataNormalizer.normalize_string(value)
        if normalized:
            # Remove special characters except underscore and hyphen
            normalized = re.sub(r'[^\w\s-]', '', normalized)
            # Replace multiple spaces with single underscore
            normalized = re.sub(r'\s+', '_', normalized)
            # Remove leading/trailing underscores
            normalized = normalized.strip('_')
            # Convert to uppercase for consistency
            normalized = normalized.upper()
        return normalized
    
    @staticmethod
    def normalize_product_code(value: Any, system: str = None) -> Optional[str]:
        """Special normalization for product codes"""
        normalized = DataNormalizer.normalize_string(value)
        if normalized:
            # Keep only alphanumeric and basic symbols based on system
            if system == 'SAP':
                # SAP codes are usually numeric
                normalized = re.sub(r'[^\d]', '', normalized)
            elif system == 'INDENT_EASY':
                # IE codes like IE-12345
                normalized = re.sub(r'[^A-Za-z0-9\-]', '', normalized)
                normalized = normalized.upper()
            elif system == 'NDDB':
                # NDDB codes like ND12345
                normalized = re.sub(r'[^A-Za-z0-9]', '', normalized)
                normalized = normalized.upper()
            else:
                # General case
                normalized = re.sub(r'[^\w\s-.#]', '', normalized)
            
            # Remove spaces
            normalized = normalized.replace(' ', '')
        return normalized
    
    @staticmethod
    def normalize_product_name(value: Any) -> Optional[str]:
        """Normalize product names"""
        normalized = DataNormalizer.normalize_string(value)
        if normalized:
            # Title case for consistency
            normalized = normalized.title()
            # Remove extra whitespace
            normalized = ' '.join(normalized.split())
        return normalized
    
    @staticmethod
    def normalize_uom(value: Any) -> Optional[str]:
        """Normalize unit of measure"""
        normalized = DataNormalizer.normalize_string(value)
        if normalized:
            normalized = normalized.upper()
            # Map common variations
            uom_mapping = {
                'KGS': 'KG',
                'KILOGRAM': 'KG',
                'KILOGRAMS': 'KG',
                'L': 'LITRE',
                'LTR': 'LITRE',
                'LITERS': 'LITRE',
                'PCS': 'PIECE',
                'PCS.': 'PIECE',
                'UNITS': 'UNIT',
            }
            normalized = uom_mapping.get(normalized, normalized)
        return normalized


class ProductMappingValidator:
    """Validates product mapping data against business rules"""
    
    # Regex patterns for validation
    PRODUCT_CODE_PATTERNS = {
        'INDENT_EASY': r'^[A-Z]{2,3}-\d{3,6}$',  # IE-12345
        'SAP': r'^\d{7,10}$',  # 3600006
        'NDDB': r'^[A-Z]{2,3}\d{3,6}$',  # ND12345
    }
    
    PRODUCT_NAME_PATTERNS = {
        'INDENT_EASY': r'^[A-Z][A-Za-z0-9\s\-&]+$',  # Starts with capital, alphanumeric with spaces/hyphens
        'SAP': r'^[A-Z][A-Za-z0-9\s\-/]+$',
        'NDDB': r'^[A-Z][A-Za-z0-9\s\-]+$',
    }
    
    UOM_VALUES = {'KG', 'LITRE', 'PIECE', 'BOX', 'PACKET', 'BAG', 'CARTON', 'UNIT'}
    SYSTEM_VALUES = {'INDENT_EASY', 'SAP', 'NDDB'}
    
    @classmethod
    def validate_row(cls, row: Dict, row_index: int, 
                    existing_groups: Dict[str, Dict],
                    existing_mappings: Dict[Tuple[str, str], Dict]) -> List[ValidationError]:
        """Validate a single row of data"""
        errors = []
        
        # 1. Validate group name
        group_name = row.get('Group Name')
        if not group_name or pd.isna(group_name):
            errors.append(ValidationError(
                row_index=row_index,
                field='Group Name',
                value=str(group_name),
                rule=ValidationRule.GROUP_NAME_REQUIRED,
                error_message='Group Name is required',
                suggestion='Provide a valid group name',
                is_critical=True
            ))
        
        # 2. Validate each system's product data
        systems = ['INDENT_EASY', 'SAP', 'NDDB']
        system_data = {}
        
        for system in systems:
            product_name = row.get(f'{system}_Product_Name')
            product_code = row.get(f'{system}_Product_Code')
            
            # Skip if no product name (optional field)
            if not product_name or pd.isna(product_name):
                continue
            
            system_data[system] = {'name': product_name, 'code': product_code}
            
            # Validate product name format
            if not cls._validate_product_name(product_name, system):
                errors.append(ValidationError(
                    row_index=row_index,
                    field=f'{system}_Product_Name',
                    value=str(product_name),
                    rule=ValidationRule.PRODUCT_NAME_FORMAT,
                    error_message=f'Invalid product name format for {system}',
                    suggestion=f'Product names should start with capital letter and contain only alphanumeric characters, spaces, hyphens',
                    is_critical=False
                ))
            
            # Validate product code format if present
            if product_code and not pd.isna(product_code):
                if not cls._validate_product_code(product_code, system):
                    errors.append(ValidationError(
                        row_index=row_index,
                        field=f'{system}_Product_Code',
                        value=str(product_code),
                        rule=ValidationRule.PRODUCT_CODE_FORMAT,
                        error_message=f'Invalid product code format for {system}',
                        suggestion=cls._get_code_format_suggestion(system),
                        is_critical=False
                    ))
            
            # Check for code in name (common data entry error)
            if product_code and not pd.isna(product_code):
                if cls._is_code_in_name(product_name, product_code):
                    errors.append(ValidationError(
                        row_index=row_index,
                        field=f'{system}_Product_Name',
                        value=str(product_name),
                        rule=ValidationRule.NO_CODE_IN_NAME,
                        error_message=f'Product name appears to contain product code for {system}',
                        suggestion='Product name should not contain product codes. Use separate fields.',
                        is_critical=False
                    ))
            
            # Check for name in code
            if product_code and not pd.isna(product_code) and product_name:
                if cls._is_name_in_code(product_name, product_code):
                    errors.append(ValidationError(
                        row_index=row_index,
                        field=f'{system}_Product_Code',
                        value=str(product_code),
                        rule=ValidationRule.NO_NAME_IN_CODE,
                        error_message=f'Product code appears to contain product name elements for {system}',
                        suggestion='Product code should be a numeric/alphanumeric identifier, not a name.',
                        is_critical=False
                    ))
        
        # 3. Check for conflicting mappings
        if group_name and system_data:
            conflict_errors = cls._check_conflicting_mappings(
                row_index, group_name, system_data, existing_groups, existing_mappings
            )
            errors.extend(conflict_errors)
        
        # 4. Validate UOM
        uom = row.get('UOM')
        if uom and not pd.isna(uom):
            normalized_uom = DataNormalizer.normalize_string(uom)
            if normalized_uom and normalized_uom.upper() not in cls.UOM_VALUES:
                errors.append(ValidationError(
                    row_index=row_index,
                    field='UOM',
                    value=str(uom),
                    rule=ValidationRule.VALID_UOM,
                    error_message=f'Invalid Unit of Measure: {uom}',
                    suggestion=f'Valid UOM values: {", ".join(sorted(cls.UOM_VALUES))}',
                    is_critical=False
                ))
        
        # 5. Validate primary system
        primary_system = row.get('Is_Primary')
        if primary_system and not pd.isna(primary_system):
            primary_system = DataNormalizer.normalize_string(primary_system)
            if primary_system and primary_system.upper() not in cls.SYSTEM_VALUES:
                errors.append(ValidationError(
                    row_index=row_index,
                    field='Is_Primary',
                    value=str(primary_system),
                    rule=ValidationRule.PRIMARY_SYSTEM_VALIDATION,
                    error_message=f'Invalid primary system: {primary_system}',
                    suggestion='Primary system must be one of: INDENT_EASY, SAP, NDDB',
                    is_critical=False
                ))
            # Check if primary system has product data
            elif primary_system.upper() not in system_data:
                errors.append(ValidationError(
                    row_index=row_index,
                    field='Is_Primary',
                    value=str(primary_system),
                    rule=ValidationRule.PRIMARY_SYSTEM_VALIDATION,
                    error_message=f'Primary system {primary_system} does not have product data',
                    suggestion='Provide product name for primary system or change primary system',
                    is_critical=True
                ))
        
        return errors
    
    @classmethod
    def _check_conflicting_mappings(cls, row_index: int, group_name: str, 
                                   system_data: Dict[str, Dict],
                                   existing_groups: Dict[str, Dict],
                                   existing_mappings: Dict[Tuple[str, str], Dict]) -> List[ValidationError]:
        """Check for conflicting mappings with existing data"""
        errors = []
        
        # Check if mappings already exist in other groups
        for system, data in system_data.items():
            product_name = data['name']
            mapping_key = (system, product_name)
            
            if mapping_key in existing_mappings:
                mapping = existing_mappings[mapping_key]
                
                # Find which group this mapping belongs to
                for existing_group_name, group_info in existing_groups.items():
                    group_id = group_info['id']
                    if group_id in group_info.get('mappings', {}):
                        if mapping['id'] in group_info['mappings'][group_id]:
                            # Found conflicting mapping in different group
                            if existing_group_name != group_name:
                                errors.append(ValidationError(
                                    row_index=row_index,
                                    field=f'{system}_Product_Name',
                                    value=product_name,
                                    rule=ValidationRule.CONFLICTING_MAPPINGS,
                                    error_message=f'Product "{product_name}" for system {system} already exists in group "{existing_group_name}"',
                                    suggestion=f'Use existing group "{existing_group_name}" or create new mapping',
                                    is_critical=True
                                ))
                            break
        
        return errors
    
    @classmethod
    def _validate_product_name(cls, product_name: str, system: str) -> bool:
        """Validate product name format"""
        if not product_name or pd.isna(product_name):
            return False
        
        pattern = cls.PRODUCT_NAME_PATTERNS.get(system, cls.PRODUCT_NAME_PATTERNS['INDENT_EASY'])
        return bool(re.match(pattern, str(product_name)))
    
    @classmethod
    def _validate_product_code(cls, product_code: str, system: str) -> bool:
        """Validate product code format"""
        if not product_code or pd.isna(product_code):
            return True
        
        pattern = cls.PRODUCT_CODE_PATTERNS.get(system)
        if not pattern:
            return True  # No validation pattern for this system
        
        code_str = str(product_code)
        # Remove common prefixes/suffixes
        code_str = re.sub(r'^(IE|SAP|NDDB)[_\-\s]*', '', code_str, flags=re.IGNORECASE)
        return bool(re.match(pattern, code_str))
    
    @classmethod
    def _get_code_format_suggestion(cls, system: str) -> str:
        """Get suggestion for code format"""
        suggestions = {
            'INDENT_EASY': 'Format: IE-12345 (2-3 letters, hyphen, 3-6 digits)',
            'SAP': 'Format: 3600006 (7-10 digits)',
            'NDDB': 'Format: ND12345 (2-3 letters followed by 3-6 digits)'
        }
        return suggestions.get(system, 'Check the format for this system')
    
    @classmethod
    def _is_code_in_name(cls, product_name: str, product_code: str) -> bool:
        """Check if product code appears in product name"""
        name_str = str(product_name).lower()
        code_str = str(product_code).lower()
        
        # Remove common prefixes
        code_clean = re.sub(r'^(ie|sap|nddb)[_\-\s]*', '', code_str)
        
        # Check if code (or significant part) is in name
        if code_clean and len(code_clean) >= 3:
            return code_clean in name_str
        
        return False
    
    @classmethod
    def _is_name_in_code(cls, product_name: str, product_code: str) -> bool:
        """Check if product name elements appear in product code"""
        name_words = set(str(product_name).lower().split())
        code_str = str(product_code).lower()
        
        # Check for any name word (3+ chars) in code
        for word in name_words:
            if len(word) >= 3 and word in code_str:
                return True
        
        return False


class LookupCache:
    """In-memory cache for database lookups to minimize queries"""
    
    def __init__(self):
        self.groups_by_name: Dict[str, Dict] = {}
        self.groups_by_id: Dict[int, Dict] = {}
        self.mappings_by_system_name: Dict[Tuple[str, str], Dict] = {}
        self.mappings_by_system_code: Dict[Tuple[str, str], Dict] = {}
        self.mappings_by_id: Dict[int, Dict] = {}
        self.group_mappings: Dict[int, Set[int]] = {}
        self.primary_mappings: Dict[int, int] = {}  # group_id -> primary_mapping_id
        self.mapping_groups: Dict[int, Set[int]] = {}  # mapping_id -> set of group_ids
        
    def load_from_database(self):
        """Load all relevant data from database"""
        # Clear existing data
        self.clear()
        
        # Load groups
        groups = ProductMappingGroup.objects.filter(is_active=True).select_related()
        for group in groups:
            group_info = {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'is_active': group.is_active,
                'created_at': group.created_at,
                'updated_at': group.updated_at
            }
            self.groups_by_name[group.name] = group_info
            self.groups_by_id[group.id] = group_info
            self.group_mappings[group.id] = set()
        
        # Load mappings
        mappings = ProductMapping.objects.filter(is_active=True).select_related()
        for mapping in mappings:
            mapping_info = {
                'id': mapping.id,
                'system': mapping.system,
                'product_name': mapping.product_name,
                'product_code': mapping.product_code,
                'description': mapping.description,
                'uom': mapping.uom,
                'size': mapping.size,
                'material_type': mapping.material_type,
                'is_active': mapping.is_active,
                'created_at': mapping.created_at,
                'updated_at': mapping.updated_at
            }
            
            # Index by system and name
            key_name = (mapping.system, mapping.product_name)
            self.mappings_by_system_name[key_name] = mapping_info
            
            # Index by system and code if code exists
            if mapping.product_code:
                key_code = (mapping.system, mapping.product_code)
                self.mappings_by_system_code[key_code] = mapping_info
            
            # Index by ID
            self.mappings_by_id[mapping.id] = mapping_info
            self.mapping_groups[mapping.id] = set()
        
        # Load relations and build group-mapping relationships
        relations = ProductMappingRelation.objects.select_related('group', 'product_mapping')
        for relation in relations:
            group_id = relation.group_id
            mapping_id = relation.product_mapping_id
            
            if group_id in self.group_mappings:
                self.group_mappings[group_id].add(mapping_id)
            
            if mapping_id in self.mapping_groups:
                self.mapping_groups[mapping_id].add(group_id)
            
            if relation.is_primary:
                self.primary_mappings[group_id] = mapping_id
    
    def clear(self):
        """Clear all cached data"""
        self.groups_by_name.clear()
        self.groups_by_id.clear()
        self.mappings_by_system_name.clear()
        self.mappings_by_system_code.clear()
        self.mappings_by_id.clear()
        self.group_mappings.clear()
        self.primary_mappings.clear()
        self.mapping_groups.clear()
    
    def add_group(self, group: ProductMappingGroup):
        """Add a group to cache"""
        group_info = {
            'id': group.id,
            'name': group.name,
            'description': group.description,
            'is_active': group.is_active,
            'created_at': group.created_at,
            'updated_at': group.updated_at
        }
        self.groups_by_name[group.name] = group_info
        self.groups_by_id[group.id] = group_info
        self.group_mappings[group.id] = set()
    
    def add_mapping(self, mapping: ProductMapping):
        """Add a mapping to cache"""
        mapping_info = {
            'id': mapping.id,
            'system': mapping.system,
            'product_name': mapping.product_name,
            'product_code': mapping.product_code,
            'description': mapping.description,
            'uom': mapping.uom,
            'size': mapping.size,
            'material_type': mapping.material_type,
            'is_active': mapping.is_active,
            'created_at': mapping.created_at,
            'updated_at': mapping.updated_at
        }
        
        # Index by system and name
        key_name = (mapping.system, mapping.product_name)
        self.mappings_by_system_name[key_name] = mapping_info
        
        # Index by system and code if code exists
        if mapping.product_code:
            key_code = (mapping.system, mapping.product_code)
            self.mappings_by_system_code[key_code] = mapping_info
        
        # Index by ID
        self.mappings_by_id[mapping.id] = mapping_info
        self.mapping_groups[mapping.id] = set()
    
    def add_relation(self, group_id: int, mapping_id: int, is_primary: bool = False):
        """Add a relation to cache"""
        if group_id in self.group_mappings:
            self.group_mappings[group_id].add(mapping_id)
        
        if mapping_id in self.mapping_groups:
            self.mapping_groups[mapping_id].add(group_id)
        
        if is_primary:
            self.primary_mappings[group_id] = mapping_id


class ReconciliationEngine:
    """Main reconciliation engine for product mapping across systems"""
    
    def __init__(self, user_id: Optional[int] = None, batch_id: Optional[str] = None):
        self.user_id = user_id
        self.batch_id = batch_id or str(uuid.uuid4())
        self.normalizer = DataNormalizer()
        self.validator = ProductMappingValidator()
        self.cache = LookupCache()
        self.metrics = ProcessingMetrics()
        self.errors: List[ValidationError] = []
        self.audit_logs: List[Dict] = []
        
        # Processing state
        self.processing_start_time = timezone.now()
        self.current_phase = None
        self.upload_record = None
        self.upload_batch = None
        
    def process_excel_file(self, excel_file, chunk_size: int = 1000) -> Dict[str, Any]:
        """
        Main entry point: Process Excel file with chunked reading
        Handles specific Excel template format with merged header rows
        """
        try:
        # Update phase
            self._update_phase(ProcessingPhase.FILE_LOADING)
            
            # Create upload record - this now creates both UploadBatch and ProductMappingUpload
            self._create_upload_record(excel_file)
            
            # Load cache
            self._update_phase(ProcessingPhase.VALIDATION)
            self.cache.load_from_database()
            
            # Read Excel file with specific handling for your template
            try:
                # Try to read with header at row 4 (0-indexed, so row 5 in Excel)
                excel_data = pd.read_excel(
                    excel_file,
                    sheet_name=0,
                    header=4,  # Row 5 is the header (0-indexed)
                    dtype=str,
                    keep_default_na=False,
                    engine='openpyxl'  # Use openpyxl for better Excel handling
                )
            except Exception as e:
                logger.warning(f"Failed to read with header=4: {e}. Trying manual parsing.")
                
                # Manual parsing for problematic Excel files
                excel_data = pd.read_excel(
                    excel_file,
                    sheet_name=0,
                    header=None,  # Don't use any row as header
                    dtype=str,
                    keep_default_na=False,
                    engine='openpyxl'
                )
                
                # Find the header row (look for 'Group Name' in the first column)
                header_row = None
                for i in range(min(10, len(excel_data))):  # Check first 10 rows
                    cell_value = str(excel_data.iloc[i, 0])
                    if 'Group Name' in cell_value:
                        header_row = i
                        break
                
                if header_row is None:
                    # Try alternative: look for 'GROUP INFORMATION' in row 0
                    if 'GROUP INFORMATION' in str(excel_data.iloc[0, 0]):
                        header_row = 4  # Assuming header is row 5 (0-indexed 4)
                    else:
                        raise ValueError("Could not identify header row in Excel file")
                
                # Use the found header row
                excel_data.columns = excel_data.iloc[header_row]
                excel_data = excel_data.iloc[header_row + 1:].reset_index(drop=True)
            
            # Clean column names
            excel_data.columns = [str(col).strip() if pd.notna(col) else f'col_{i}' 
                                for i, col in enumerate(excel_data.columns)]
            
            # Debug output
            print(f"Columns found: {list(excel_data.columns)}")
            print(f"First few rows:\n{excel_data.head(3)}")
            
            # Handle specific column names from your template
            column_mapping = {
                'Group Name': 'Group Name',
                'Group Description': 'Group Description',
                'INDENT_EASY_Product_Name': 'INDENT_EASY_Product_Name',
                'INDENT_EASY_Product_Code': 'INDENT_EASY_Product_Code',
                'SAP_Product_Name': 'SAP_Product_Name',
                'SAP_Product_Code': 'SAP_Product_Code',
                'NDDB_Product_Name': 'NDDB_Product_Name',
                'NDDB_Product_Code': 'NDDB_Product_Code',
                'UOM': 'UOM',
                'Size': 'Size',
                'Material_Type': 'Material_Type',
                'Is_Primary': 'Is_Primary'
            }
            
            # Rename columns to standard names
            for actual_col in excel_data.columns:
                actual_lower = str(actual_col).lower().replace(' ', '_')
                for std_col in column_mapping.keys():
                    std_lower = std_col.lower().replace(' ', '_')
                    if std_lower in actual_lower or actual_lower in std_lower:
                        excel_data = excel_data.rename(columns={actual_col: std_col})
                        print(f"Renamed '{actual_col}' to '{std_col}'")
                        break
            
            # Check for required columns
            required_columns = ['Group Name']
            missing_columns = [col for col in required_columns if col not in excel_data.columns]
            
            if missing_columns:
                # Try to find them with different naming
                for missing_col in missing_columns:
                    for actual_col in excel_data.columns:
                        if missing_col.lower().replace(' ', '_') in actual_col.lower().replace(' ', '_'):
                            excel_data = excel_data.rename(columns={actual_col: missing_col})
                            missing_columns.remove(missing_col)
                            print(f"Found and renamed '{actual_col}' to '{missing_col}'")
                            break
                
                if missing_columns:
                    raise ValueError(f"Missing required columns: {missing_columns}. Available columns: {list(excel_data.columns)}")
            
            # Clean data - remove empty rows
            excel_data = excel_data[excel_data['Group Name'].notna() & (excel_data['Group Name'] != '')]
            
            # Reset index after cleaning
            excel_data = excel_data.reset_index(drop=True)
            
            total_rows = len(excel_data)
            self.metrics.total_rows = total_rows
            
            if total_rows == 0:
                raise ValueError("No valid data rows found after cleaning")
            
            print(f"Total valid rows to process: {total_rows}")
            
            # Update upload record with total rows
            self.upload_record.metrics = {'total_rows': total_rows}
            self.upload_record.save()
            
            # Process in chunks
            self._update_phase(ProcessingPhase.NORMALIZATION)
            
            for chunk_start in range(0, total_rows, chunk_size):
                chunk_end = min(chunk_start + chunk_size, total_rows)
                chunk = excel_data.iloc[chunk_start:chunk_end]
                
                self._process_chunk(chunk, chunk_start)
                
                # Update progress
                progress = min(80, (chunk_end / total_rows) * 100)
                self._update_progress(progress)
            
            # Finalize processing
            self._finalize_processing()
            
            return self._build_response()
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._log_error(error_msg, is_critical=True)
            
            # Update both records with error
            if self.upload_batch:
                self.upload_batch.status = 'FAILED'
                self.upload_batch.error_summary = {'error': error_msg}
                self.upload_batch.processing_completed_at = timezone.now()
                self.upload_batch.save()
            
            if self.upload_record:
                self.upload_record.status = 'FAILED'
                self.upload_record.error_message = error_msg
                self.upload_record.completed_at = timezone.now()
                self.upload_record.save()
            
            raise
    
    def _process_chunk(self, chunk: pd.DataFrame, chunk_start_index: int):
        """Process a chunk of data"""
        for idx, row in chunk.iterrows():
            absolute_row_index = chunk_start_index + idx + 1  # +1 for 1-based indexing
            
            try:
                # Normalize row data
                normalized_row = self._normalize_row(row.to_dict())
                
                # Validate row
                validation_errors = self.validator.validate_row(
                    normalized_row,
                    absolute_row_index,
                    self.cache.groups_by_name,
                    self.cache.mappings_by_system_name
                )
                
                if validation_errors:
                    critical_errors = [e for e in validation_errors if e.is_critical]
                    non_critical_errors = [e for e in validation_errors if not e.is_critical]
                    
                    # Log all errors
                    self.errors.extend(validation_errors)
                    
                    # Log critical errors to database
                    if critical_errors:
                        self._log_errors(critical_errors)
                        self.metrics.rows_rejected += 1
                        continue
                    
                    # For non-critical errors, we can still process but log them
                    if non_critical_errors:
                        self._log_errors(non_critical_errors)
                
                self.metrics.rows_validated += 1
                
                # Reconcile row
                result = self._reconcile_row(normalized_row, absolute_row_index)
                
                # Apply reconciliation result
                if result.action != ReconciliationAction.REJECT:
                    try:
                        with transaction.atomic():
                            self._apply_reconciliation(result)
                            self.metrics.rows_processed += 1
                    except Exception as e:
                        # Log transaction error but continue processing
                        error_msg = f"Failed to apply reconciliation for row {absolute_row_index}: {str(e)}"
                        self._log_error(error_msg, row_index=absolute_row_index, is_critical=False)
                        self.metrics.rows_rejected += 1
                else:
                    self.metrics.rows_rejected += 1
                
                # Update metrics
                self._update_metrics_from_result(result)
                
            except Exception as e:
                # Log row-level error but continue processing
                error_msg = f"Error processing row {absolute_row_index}: {str(e)}"
                self._log_error(error_msg, row_index=absolute_row_index, is_critical=False)
                self.metrics.rows_rejected += 1
                logger.error(error_msg, exc_info=True)
    
    def _normalize_row(self, row: Dict) -> Dict:
        """Normalize all values in a row"""
        normalized = {}
        
        for key, value in row.items():
            if pd.isna(value) or value == '':
                normalized[key] = None
            elif key == 'Group Name':
                normalized[key] = self.normalizer.normalize_group_name(value)
            elif key == 'Group Description':
                normalized[key] = self.normalizer.normalize_string(value)
            elif key.endswith('_Product_Code'):
                # Extract system from column name
                system = key.replace('_Product_Code', '')
                normalized[key] = self.normalizer.normalize_product_code(value, system)
            elif key.endswith('_Product_Name'):
                normalized[key] = self.normalizer.normalize_product_name(value)
            elif key in ['UOM', 'Size', 'Material_Type', 'Material Type']:
                if key == 'UOM':
                    normalized[key] = self.normalizer.normalize_uom(value)
                else:
                    normalized[key] = self.normalizer.normalize_string(value)
            elif key == 'Is_Primary':
                normalized[key] = self.normalizer.normalize_string(value)
                if normalized[key]:
                    normalized[key] = normalized[key].upper()
            else:
                normalized[key] = value
        
        return normalized
    
    def _reconcile_row(self, row: Dict, row_index: int) -> ReconciliationResult:
        """
        Reconcile a single row: decide create/update/merge/skip
        This is the core logic for mapping products across systems
        """
        group_name = row['Group Name']
        
        # Check if group exists
        group_data = self.cache.groups_by_name.get(group_name)
        
        if group_data:
            # Group exists - update or relate scenario
            return self._reconcile_existing_group(row, row_index, group_data)
        else:
            # New group - create or merge scenario
            return self._reconcile_new_group(row, row_index)
    
    def _reconcile_existing_group(self, row: Dict, row_index: int, 
                                 group_data: Dict) -> ReconciliationResult:
        """Reconcile row for existing group"""
        group_id = group_data['id']
        group_name = group_data['name']
        changes = {}
        mapping_actions = []
        
        # Check if group description changed
        new_description = row.get('Group Description')
        if new_description and new_description != group_data.get('description'):
            changes['description'] = new_description
        
        # Get existing mappings for this group
        existing_group_mappings = self.cache.group_mappings.get(group_id, set())
        
        # Process each system's mapping
        systems = ['INDENT_EASY', 'SAP', 'NDDB']
        
        for system in systems:
            product_name = row.get(f'{system}_Product_Name')
            if not product_name:
                continue
                
            product_code = row.get(f'{system}_Product_Code')
            uom = row.get('UOM')
            size = row.get('Size') or row.get('Material Type')  # Handle both column names
            material_type = row.get('Material_Type')
            
            # Check if mapping exists in the system
            mapping_key = (system, product_name)
            mapping_data = self.cache.mappings_by_system_name.get(mapping_key)
            
            # Determine action for this mapping
            action_info = self._determine_mapping_action(
                system=system,
                product_name=product_name,
                product_code=product_code,
                uom=uom,
                size=size,
                material_type=material_type,
                existing_mapping=mapping_data,
                group_id=group_id,
                existing_group_mappings=existing_group_mappings,
                should_be_primary=row.get('Is_Primary') == system
            )
            
            mapping_actions.append(action_info)
        
        # Check for conflicts within this row
        self._check_mapping_conflicts(mapping_actions, row_index)
        
        # Determine overall action
        has_updates = bool(changes)
        has_mapping_changes = any(
            action['action'] in [ReconciliationAction.CREATE, ReconciliationAction.UPDATE, ReconciliationAction.MERGE]
            for action in mapping_actions
        )
        
        if has_updates or has_mapping_changes:
            action = ReconciliationAction.UPDATE
        else:
            action = ReconciliationAction.SKIP
        
        return ReconciliationResult(
            row_index=row_index,
            action=action,
            entity_type='GROUP',
            entity_id=group_id,
            entity_identifier=group_name,
            changes=changes,
            mapping_actions=mapping_actions
        )
    
    def _reconcile_new_group(self, row: Dict, row_index: int) -> ReconciliationResult:
        """Reconcile row for new group"""
        group_name = row['Group Name']
        changes = {'description': row.get('Group Description')}
        mapping_actions = []
        
        # Check if any of the mappings already exist in other groups
        existing_mappings_info = []
        
        for system in ['INDENT_EASY', 'SAP', 'NDDB']:
            product_name = row.get(f'{system}_Product_Name')
            if not product_name:
                continue
                
            product_code = row.get(f'{system}_Product_Code')
            uom = row.get('UOM')
            size = row.get('Size') or row.get('Material Type')
            material_type = row.get('Material_Type')
            
            # Check if mapping exists
            mapping_key = (system, product_name)
            mapping_data = self.cache.mappings_by_system_name.get(mapping_key)
            
            if mapping_data:
                # Find which groups this mapping belongs to
                mapping_id = mapping_data['id']
                group_ids = self.cache.mapping_groups.get(mapping_id, set())
                
                for gid in group_ids:
                    group_info = self.cache.groups_by_id.get(gid)
                    if group_info:
                        existing_mappings_info.append({
                            'system': system,
                            'product_name': product_name,
                            'existing_group': group_info['name'],
                            'mapping_id': mapping_id,
                            'mapping_data': mapping_data
                        })
            
            # Determine action for new group
            action_info = self._determine_mapping_action(
                system=system,
                product_name=product_name,
                product_code=product_code,
                uom=uom,
                size=size,
                material_type=material_type,
                existing_mapping=mapping_data,
                group_id=None,  # New group
                existing_group_mappings=set(),
                should_be_primary=row.get('Is_Primary') == system
            )
            
            mapping_actions.append(action_info)
        
        # If mappings exist in other groups, we need to decide what to do
        if existing_mappings_info:
            # For now, we'll create a new group but mark for merge review
            # In production, you might implement automatic merging logic here
            
            # Create error for manual review
            conflict_details = ', '.join([
                f"{info['system']}:{info['product_name']} in group '{info['existing_group']}'"
                for info in existing_mappings_info
            ])
            
            return ReconciliationResult(
                row_index=row_index,
                action=ReconciliationAction.REJECT,
                entity_type='GROUP',
                entity_id=None,
                entity_identifier=group_name,
                changes=changes,
                mapping_actions=mapping_actions,
                errors=[ValidationError(
                    row_index=row_index,
                    field='Group Name',
                    value=group_name,
                    rule=ValidationRule.CONFLICTING_MAPPINGS,
                    error_message=f'Some product mappings already exist in other groups: {conflict_details}',
                    suggestion='These mappings need to be merged manually. Please review.',
                    is_critical=True
                )]
            )
        
        # All mappings are new - create new group
        return ReconciliationResult(
            row_index=row_index,
            action=ReconciliationAction.CREATE,
            entity_type='GROUP',
            entity_id=None,
            entity_identifier=group_name,
            changes=changes,
            mapping_actions=mapping_actions
        )
    
    def _determine_mapping_action(self, system: str, product_name: str, product_code: Optional[str],
                                 uom: Optional[str], size: Optional[str], material_type: Optional[str],
                                 existing_mapping: Optional[Dict], group_id: Optional[int],
                                 existing_group_mappings: Set[int], should_be_primary: bool) -> Dict:
        """Determine what action to take for a mapping"""
        
        if not existing_mapping:
            # New mapping - need to create
            return {
                'action': ReconciliationAction.CREATE,
                'system': system,
                'product_name': product_name,
                'product_code': product_code,
                'uom': uom,
                'size': size,
                'material_type': material_type,
                'is_primary': should_be_primary,
                'existing_mapping_id': None
            }
        
        # Mapping exists
        mapping_id = existing_mapping['id']
        
        # Check if mapping is already in this group
        if group_id and mapping_id in existing_group_mappings:
            # Mapping already in this group - check for updates
            changes = {}
            
            # Check for field changes
            field_checks = [
                ('product_code', product_code),
                ('uom', uom),
                ('size', size),
                ('material_type', material_type)
            ]
            
            for field, new_value in field_checks:
                old_value = existing_mapping.get(field)
                if new_value and new_value != old_value:
                    changes[field] = {'old': old_value, 'new': new_value}
            
            # Check if primary status changed
            current_primary = self.cache.primary_mappings.get(group_id)
            if should_be_primary and current_primary != mapping_id:
                changes['is_primary'] = {'old': current_primary == mapping_id, 'new': True}
            
            if changes:
                return {
                    'action': ReconciliationAction.UPDATE,
                    'system': system,
                    'product_name': product_name,
                    'existing_mapping_id': mapping_id,
                    'changes': changes,
                    'is_primary': should_be_primary
                }
            else:
                return {
                    'action': ReconciliationAction.SKIP,
                    'system': system,
                    'product_name': product_name,
                    'existing_mapping_id': mapping_id,
                    'is_primary': should_be_primary
                }
        else:
            # Mapping exists but not in this group - need to relate or merge
            return {
                'action': ReconciliationAction.RELATE,
                'system': system,
                'product_name': product_name,
                'existing_mapping_id': mapping_id,
                'is_primary': should_be_primary,
                'note': f'Mapping exists in different group(s): {self.cache.mapping_groups.get(mapping_id, set())}'
            }
    
    def _check_mapping_conflicts(self, mapping_actions: List[Dict], row_index: int):
        """Check for conflicts in mapping actions"""
        # Group by system to check for duplicates
        by_system = {}
        for action in mapping_actions:
            system = action['system']
            if system not in by_system:
                by_system[system] = []
            by_system[system].append(action)
        
        # Check each system for multiple mappings
        for system, actions in by_system.items():
            if len(actions) > 1:
                # Multiple mappings for same system - this is an error
                product_names = [action['product_name'] for action in actions]
                self.errors.append(ValidationError(
                    row_index=row_index,
                    field=f'{system}_Product_Name',
                    value=', '.join(product_names),
                    rule=ValidationRule.UNIQUE_MAPPING_PER_SYSTEM,
                    error_message=f'Multiple product mappings for same system ({system})',
                    suggestion='Each system should have only one product mapping per group',
                    is_critical=True
                ))
    
    def _apply_reconciliation(self, result: ReconciliationResult):
        """Apply reconciliation result to database and cache"""
        if result.action == ReconciliationAction.CREATE:
            self._create_group_with_mappings(result)
        elif result.action == ReconciliationAction.UPDATE:
            self._update_group_and_mappings(result)
        elif result.action == ReconciliationAction.RELATE:
            self._relate_mappings(result)
        elif result.action == ReconciliationAction.SKIP:
            self._log_skipped(result)
    
    def _create_group_with_mappings(self, result: ReconciliationResult):
        """Create new group with all its mappings"""
        # Create group
        group = ProductMappingGroup.objects.create(
            name=result.entity_identifier,
            description=result.changes.get('description'),
            created_at=timezone.now(),
            updated_at=timezone.now()
        )
        
        # Add to cache
        self.cache.add_group(group)
        
        # Process each mapping action
        primary_mapping_id = None
        
        for action in result.mapping_actions:
            if action['action'] == ReconciliationAction.CREATE:
                # Create new mapping
                mapping = ProductMapping.objects.create(
                    system=action['system'],
                    product_name=action['product_name'],
                    product_code=action.get('product_code'),
                    uom=action.get('uom'),
                    size=action.get('size'),
                    material_type=action.get('material_type'),
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )
                
                # Add to cache
                self.cache.add_mapping(mapping)
                
                # Create relation
                is_primary = action.get('is_primary', False)
                relation = ProductMappingRelation.objects.create(
                    group=group,
                    product_mapping=mapping,
                    is_primary=is_primary
                )
                
                # Add to cache
                self.cache.add_relation(group.id, mapping.id, is_primary)
                
                if is_primary:
                    primary_mapping_id = mapping.id
                
                # Update metrics
                self.metrics.mappings_created += 1
                self.metrics.relations_created += 1
        
        # Log audit
        self._log_audit(
            action=ReconciliationAction.CREATE.value,
            entity_type='GROUP',
            entity_id=group.id,
            entity_identifier=group.name,
            changes=result.changes,
            row_index=result.row_index
        )
        
        # Update metrics
        self.metrics.groups_created += 1
    
    def _update_group_and_mappings(self, result: ReconciliationResult):
        """Update existing group and its mappings"""
        group = ProductMappingGroup.objects.get(id=result.entity_id)
        
        # Update group if needed
        if 'description' in result.changes:
            group.description = result.changes['description']
            group.updated_at = timezone.now()
            group.save()
            
            # Update cache
            if group.name in self.cache.groups_by_name:
                self.cache.groups_by_name[group.name]['description'] = group.description
                self.cache.groups_by_name[group.name]['updated_at'] = group.updated_at
        
        # Process each mapping action
        for action in result.mapping_actions:
            if action['action'] == ReconciliationAction.CREATE:
                # Create new mapping and relate to group
                mapping = ProductMapping.objects.create(
                    system=action['system'],
                    product_name=action['product_name'],
                    product_code=action.get('product_code'),
                    uom=action.get('uom'),
                    size=action.get('size'),
                    material_type=action.get('material_type'),
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )
                
                # Add to cache
                self.cache.add_mapping(mapping)
                
                # Create relation
                is_primary = action.get('is_primary', False)
                ProductMappingRelation.objects.create(
                    group=group,
                    product_mapping=mapping,
                    is_primary=is_primary
                )
                
                # Add to cache
                self.cache.add_relation(group.id, mapping.id, is_primary)
                
                # Update metrics
                self.metrics.mappings_created += 1
                self.metrics.relations_created += 1
                
            elif action['action'] == ReconciliationAction.UPDATE:
                # Update existing mapping
                mapping = ProductMapping.objects.get(id=action['existing_mapping_id'])
                changes = action.get('changes', {})
                
                for field, change_info in changes.items():
                    if field == 'is_primary':
                        # Update primary status in relation
                        relation = ProductMappingRelation.objects.get(
                            group=group,
                            product_mapping=mapping
                        )
                        relation.is_primary = change_info['new']
                        relation.save()
                        
                        # Update cache
                        if change_info['new']:
                            self.cache.primary_mappings[group.id] = mapping.id
                        elif self.cache.primary_mappings.get(group.id) == mapping.id:
                            del self.cache.primary_mappings[group.id]
                    else:
                        # Update mapping field
                        setattr(mapping, field, change_info['new'])
                
                if changes:
                    mapping.updated_at = timezone.now()
                    mapping.save()
                    
                    # Update cache
                    if mapping.id in self.cache.mappings_by_id:
                        cache_entry = self.cache.mappings_by_id[mapping.id]
                        for field in ['product_code', 'uom', 'size', 'material_type']:
                            if field in changes:
                                cache_entry[field] = changes[field]['new']
                        cache_entry['updated_at'] = mapping.updated_at
                    
                    # Update metrics
                    self.metrics.mappings_updated += 1
            
            elif action['action'] == ReconciliationAction.RELATE:
                # Relate existing mapping to this group
                mapping = ProductMapping.objects.get(id=action['existing_mapping_id'])
                is_primary = action.get('is_primary', False)
                
                # Check if relation already exists
                relation, created = ProductMappingRelation.objects.get_or_create(
                    group=group,
                    product_mapping=mapping,
                    defaults={'is_primary': is_primary}
                )
                
                if not created and relation.is_primary != is_primary:
                    relation.is_primary = is_primary
                    relation.save()
                
                # Add to cache
                self.cache.add_relation(group.id, mapping.id, is_primary)
                
                # Update metrics
                if created:
                    self.metrics.relations_created += 1
                else:
                    self.metrics.relations_updated += 1
        
        # Log audit
        self._log_audit(
            action=ReconciliationAction.UPDATE.value,
            entity_type='GROUP',
            entity_id=group.id,
            entity_identifier=group.name,
            changes=result.changes,
            row_index=result.row_index
        )
        
        # Update metrics
        self.metrics.groups_updated += 1
    
    def _relate_mappings(self, result: ReconciliationResult):
        """Handle relating mappings (for merge scenarios)"""
        # This is a simplified version - in production you might want more sophisticated merge logic
        self._log_audit(
            action=ReconciliationAction.RELATE.value,
            entity_type='GROUP',
            entity_id=None,
            entity_identifier=result.entity_identifier,
            changes={'note': 'Merge/relate required - manual review needed'},
            row_index=result.row_index
        )
        
        self.metrics.merges_performed += 1
    
    def _log_skipped(self, result: ReconciliationResult):
        """Log skipped rows"""
        self._log_audit(
            action=ReconciliationAction.SKIP.value,
            entity_type='GROUP',
            entity_id=result.entity_id,
            entity_identifier=result.entity_identifier,
            changes={'note': 'No changes required'},
            row_index=result.row_index
        )
        
        self.metrics.rows_skipped += 1
    
    def _update_metrics_from_result(self, result: ReconciliationResult):
        """Update metrics based on reconciliation result"""
        # Metrics are updated in individual methods
        pass
    
    def _create_upload_record(self, excel_file):
        """Create upload records for tracking"""
        # First create UploadBatch (for ProcessingErrorLog)
        self.upload_batch = UploadBatch.objects.create(
            batch_id=self.batch_id,
            file_name=excel_file.name,
            file_size=excel_file.size,
            uploaded_by_id=self.user_id,
            uploaded_at=timezone.now(),
            status='PENDING'
        )
        
        # Then create ProductMappingUpload (for reconciliation audit)
        self.upload_record = ProductMappingUpload.objects.create(
            upload_id=self.batch_id,
            user_id=self.user_id,
            filename=excel_file.name,
            file_size=excel_file.size,
            status='PENDING',
            progress=0.0,
            started_at=timezone.now()
        )
        
        return self.upload_record
    
    def _update_phase(self, phase: ProcessingPhase):
        """Update current processing phase"""
        self.current_phase = phase
        logger.info(f"Entering phase: {phase.value}")
    
    def _update_progress(self, progress: float):
        """Update processing progress"""
        if self.upload_record:
            self.upload_record.progress = progress
            self.upload_record.save(update_fields=['progress'])
    
    def _log_error(self, message: str, row_index: Optional[int] = None, 
              is_critical: bool = True):
        """Log processing error"""
        error_log = ValidationError(
            row_index=row_index or 0,
            field='SYSTEM',
            value='',
            rule=ValidationRule.PRODUCT_NAME_REQUIRED,
            error_message=message,
            suggestion='Check system logs for details',
            is_critical=is_critical
        )
        
        self.errors.append(error_log)
        
        # Also log to database if we have an upload batch
        if self.upload_batch and row_index:  # Changed from upload_record to upload_batch
            ProcessingErrorLog.objects.create(
                batch=self.upload_batch,  # Use upload_batch, not upload_record
                row_index=row_index,
                field='SYSTEM',
                value='',
                rule='PROCESSING_ERROR',
                error_message=message,
                suggestion='Check system logs for details',
                is_critical=is_critical
            )
    
    def _log_errors(self, errors: List[ValidationError]):
        """Log multiple validation errors"""
        if not self.upload_batch:  # Changed from upload_record to upload_batch
            return
        
        error_logs = []
        for error in errors:
            error_logs.append(ProcessingErrorLog(
                batch=self.upload_batch,  # Use upload_batch, not upload_record
                row_index=error.row_index,
                field=error.field,
                value=str(error.value)[:500],
                rule=error.rule.value if hasattr(error.rule, 'value') else str(error.rule),
                error_message=error.error_message[:1000],
                suggestion=error.suggestion[:500] if error.suggestion else '',
                is_critical=error.is_critical
            ))
        
        # Bulk create for performance
        ProcessingErrorLog.objects.bulk_create(error_logs)
    
    def _log_audit(self, action: str, entity_type: str, entity_id: Optional[int],
                  entity_identifier: str, changes: Dict, row_index: int):
        """Log audit trail"""
        audit_log = ReconciliationAuditLog(
            upload=self.upload_record,
            row_index=row_index,
            action_type=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_identifier=entity_identifier,
            changes=changes,
            timestamp=timezone.now()
        )
        audit_log.save()
    
    def _finalize_processing(self):
        """Finalize processing and update records"""
        self._update_phase(ProcessingPhase.FINALIZATION)
        
        processing_time = (timezone.now() - self.processing_start_time).total_seconds() * 1000
        self.metrics.processing_time_ms = int(processing_time)
        
        # Calculate success rate
        success_rate = 0
        if self.metrics.total_rows > 0:
            success_rate = ((self.metrics.rows_processed) / self.metrics.total_rows) * 100
        
        # Determine final status
        if self.metrics.rows_rejected > 0 and success_rate < 100:
            status = 'PARTIAL_SUCCESS'
            batch_status = 'PARTIAL'
        elif self.metrics.rows_rejected == self.metrics.total_rows:
            status = 'FAILED'
            batch_status = 'FAILED'
        else:
            status = 'COMPLETED'
            batch_status = 'COMPLETED'
        
        # Update UploadBatch record
        if self.upload_batch:
            self.upload_batch.status = batch_status
            self.upload_batch.total_rows = self.metrics.total_rows
            self.upload_batch.rows_processed = self.metrics.rows_processed
            self.upload_batch.rows_succeeded = self.metrics.rows_processed - self.metrics.rows_rejected
            self.upload_batch.rows_failed = self.metrics.rows_rejected
            self.upload_batch.processing_completed_at = timezone.now()
            self.upload_batch.save()
        
        # Update ProductMappingUpload record
        self.upload_record.status = status
        self.upload_record.progress = 100.0
        self.upload_record.completed_at = timezone.now()
        
        # Prepare metrics
        metrics_dict = {
            'total_rows': self.metrics.total_rows,
            'rows_processed': self.metrics.rows_processed,
            'rows_validated': self.metrics.rows_validated,
            'rows_rejected': self.metrics.rows_rejected,
            'rows_skipped': self.metrics.rows_skipped,
            'groups_created': self.metrics.groups_created,
            'groups_updated': self.metrics.groups_updated,
            'mappings_created': self.metrics.mappings_created,
            'mappings_updated': self.metrics.mappings_updated,
            'relations_created': self.metrics.relations_created,
            'relations_updated': self.metrics.relations_updated,
            'duplicates_resolved': self.metrics.duplicates_resolved,
            'merges_performed': self.metrics.merges_performed,
            'processing_time_ms': self.metrics.processing_time_ms,
            'success_rate': success_rate
        }
        
        self.upload_record.metrics = metrics_dict
        self.upload_record.save()
        
        logger.info(f"Processing completed with status: {status}, success rate: {success_rate:.2f}%")
    
    def _build_response(self) -> Dict[str, Any]:
        """Build API response"""
        # Count errors by type
        critical_errors = sum(1 for e in self.errors if e.is_critical)
        warning_errors = sum(1 for e in self.errors if not e.is_critical)
        
        response = {
            'success': self.upload_record.status in ['COMPLETED', 'PARTIAL_SUCCESS'],
            'batch_id': self.batch_id,
            'upload_id': self.upload_record.upload_id,
            'status': self.upload_record.status,
            'message': self._get_status_message(self.upload_record.status),
            'stats': self.upload_record.metrics,
            'errors_summary': {
                'total_errors': len(self.errors),
                'critical_errors': critical_errors,
                'warning_errors': warning_errors
            },
            'timestamps': {
                'started_at': self.upload_record.started_at.isoformat(),
                'completed_at': self.upload_record.completed_at.isoformat() if self.upload_record.completed_at else None
            }
        }
        
        # Add detailed errors if any
        if self.errors:
            response['error_details'] = [
                {
                    'row_index': e.row_index,
                    'field': e.field,
                    'rule': e.rule.value if hasattr(e.rule, 'value') else str(e.rule),
                    'message': e.error_message,
                    'suggestion': e.suggestion,
                    'is_critical': e.is_critical
                }
                for e in self.errors[:100]  # Limit to first 100 errors
            ]
        
        return response
    
    def _get_status_message(self, status: str) -> str:
        """Get human-readable status message"""
        messages = {
            'COMPLETED': 'Processing completed successfully',
            'PARTIAL_SUCCESS': 'Processing completed with some errors',
            'FAILED': 'Processing failed due to errors',
            'PENDING': 'Processing is pending',
            'PROCESSING': 'Processing is in progress',
            'CANCELLED': 'Processing was cancelled'
        }
        return messages.get(status, 'Processing completed')


# Utility function for API views
def process_product_mapping_upload(file, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Public API function to process product mapping uploads
    
    Args:
        file: Uploaded Excel file
        user_id: Optional user ID for auditing
    
    Returns:
        Dict with processing results
    """
    engine = ReconciliationEngine(user_id=user_id)
    return engine.process_excel_file(file)


# Example Excel template structure:
"""
Expected Excel columns:
- Group Name: Name for the product group (required)
- Group Description: Optional description
- INDENT_EASY_Product_Name: Product name in Indent Easy system
- INDENT_EASY_Product_Code: Product code in Indent Easy system
- SAP_Product_Name: Product name in SAP system
- SAP_Product_Code: Product code in SAP system
- NDDB_Product_Name: Product name in NDDB system
- NDDB_Product_Code: Product code in NDDB system
- UOM: Unit of measure
- Size: Product size
- Material_Type: Type of material
- Is_Primary: Which system is primary (INDENT_EASY, SAP, or NDDB)

Example row:
Group Name,Group Description,INDENT_EASY_Product_Name,INDENT_EASY_Product_Code,SAP_Product_Name,SAP_Product_Code,NDDB_Product_Name,NDDB_Product_Code,UOM,Size,Material_Type,Is_Primary
MILK_POWDER,Milk powder product group,Milk Powder IE,IE-12345,Milk Powder SAP,3600006,Milk Powder NDDB,ND12345,KG,1KG,Powder,INDENT_EASY
"""