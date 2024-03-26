import logging
import re
from collections import defaultdict
from typing import Dict, List

logger = logging.getLogger('ContentBundling')


def group_content_by_number(content_list: List[str], min_group_size=2) -> Dict[str, List[str]]:
    """
    Group content by the first number in the title. Returned groups keep the order in which it was found in the input.
    Args:
        content_list: list of content titles
        min_group_size: minimum number of content items in a group. In the case of a group with fewer items, it will
            not be included in the result.

    Returns:
        dict: group number as key and list of content titles as value
    """
    groups = defaultdict(list)
    for title in content_list:
        if m := re.search(r'\d+', title):
            if first_number := m.group(0).lstrip('0'):
                groups[first_number].append(title)

    filtered_groups = {k: v for k, v in groups.items() if len(v) >= min_group_size}
    return filtered_groups
