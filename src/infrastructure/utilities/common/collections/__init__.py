"""Collection utility functions organized by responsibility."""

# Import all functions from submodules
from src.infrastructure.utilities.common.collections.filtering import *
from src.infrastructure.utilities.common.collections.grouping import *
from src.infrastructure.utilities.common.collections.transforming import *
from src.infrastructure.utilities.common.collections.validation import *

# Export commonly used functions
__all__ = [
    # Validation functions
    "is_empty",
    "is_not_empty",
    "is_sorted",
    "all_match",
    "any_match",
    "none_match",
    "is_subset",
    "is_superset",
    "is_disjoint",
    # Filtering functions
    "filter_by",
    "find",
    "find_index",
    "contains",
    "contains_all",
    "contains_any",
    "distinct",
    "distinct_by",
    "remove_duplicates",
    "find_duplicates",
    "has_duplicates",
    # Transformation functions
    "map_values",
    "map_keys",
    "flatten",
    "deep_flatten",
    "chunk",
    "to_dict",
    "to_dict_with_transform",
    "to_list",
    "to_set",
    "to_tuple",
    "invert_dict",
    "merge_dicts",
    "deep_merge_dicts",
    # Grouping functions
    "group_by",
    "partition",
    "count_by",
    "count_occurrences",
    "frequency_map",
    "most_common",
    "least_common",
]
