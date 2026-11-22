"""Compatibility import for print-agent models owned by print_center."""
from backend.models.print_center import PrintAgentCredential, PrintAgentPairing

__all__ = ["PrintAgentCredential", "PrintAgentPairing"]
