"""
Dr.R L - Literature Search AI Agent
Source Package
"""

from .dr_r_agent import DrRLAgent
from .utils import log_error, log_warning, log_search, rate_limit_request

__version__ = '1.0.0'
__author__ = 'Dr.R Team'

__all__ = [
    'DrRLAgent',
    'log_error',
    'log_warning', 
    'log_search',
    'rate_limit_request'
]
