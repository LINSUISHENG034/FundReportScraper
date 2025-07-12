"""Parsers package initialization."""

from .xbrl_parser import (
    XBRLParser, XBRLParseError,
    AssetAllocation, TopHolding, IndustryAllocation, FundBasicInfo
)

__all__ = [
    "XBRLParser", "XBRLParseError",
    "AssetAllocation", "TopHolding", "IndustryAllocation", "FundBasicInfo"
]