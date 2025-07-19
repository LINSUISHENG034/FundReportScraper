"""iXBRL Extractor Module

This module provides the iXBRLExtractor class for extracting pure XBRL content
from iXBRL (Inline XBRL) HTML files.
"""

import tempfile
from pathlib import Path
from typing import Optional

from lxml import etree

from src.core.logging import get_logger


class iXBRLExtractor:
    """Extractor for iXBRL (Inline XBRL) content from HTML files.
    
    This class is responsible for extracting embedded XBRL content from iXBRL HTML files
    and providing it as clean XBRL XML for further processing by ArelleParser.
    """
    
    def __init__(self):
        """Initialize the iXBRLExtractor with an HTML parser.
        
        The parser is configured with recover=True to handle potentially
        malformed HTML gracefully.
        """
        self.html_parser = etree.HTMLParser(recover=True)
        self.logger = get_logger("parser.ixbrl_extractor")
    
    def extract_to_string(self, html_content: str) -> Optional[str]:
        """Extract XBRL content from iXBRL HTML and return as XML string.
        
        Args:
            html_content: The iXBRL HTML content as a string
            
        Returns:
            The extracted XBRL XML as a UTF-8 encoded string, or None if no XBRL content found
        """
        try:
            # Parse the HTML content
            tree = etree.fromstring(html_content.encode('utf-8'), self.html_parser)
            
            # Try primary XPath expression to find XBRL root element
            xbrl_elements = tree.xpath("//body//*[local-name()='xbrl']")
            
            # If primary expression fails, try backup expression
            if not xbrl_elements:
                xbrl_elements = tree.xpath("//*[local-name()='xbrl']")
            
            # If still no XBRL elements found, return None
            if not xbrl_elements:
                self.logger.warning("No XBRL elements found in the provided content. Source may not be a valid iXBRL file.")
                return None
            
            # Take the first XBRL element found
            xbrl_root = xbrl_elements[0]
            
            # Serialize the XBRL element and its children to XML string
            xml_bytes = etree.tostring(
                xbrl_root, 
                encoding='utf-8', 
                xml_declaration=True,
                pretty_print=True
            )
            
            xml_content = xml_bytes.decode('utf-8')
            self.logger.info("Successfully extracted XBRL content from iXBRL source.")
            return xml_content
            
        except Exception as e:
            # If any error occurs during parsing or extraction, return None
            self.logger.warning(
                "Failed to extract XBRL content due to parsing error. Source may not be a valid iXBRL file.", 
                exc_info=True
            )
            return None
    
    def extract_to_tempfile(self, html_content: str) -> Optional[Path]:
        """Extract XBRL content from iXBRL HTML and write to a temporary file.
        
        Args:
            html_content: The iXBRL HTML content as a string
            
        Returns:
            Path object pointing to the temporary file containing the XBRL XML,
            or None if no XBRL content found
        """
        # First extract the XBRL content as string
        xml_content = self.extract_to_string(html_content)
        
        if xml_content is None:
            return None
        
        try:
            # Create a temporary file and write the XML content
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.xbrl',
                encoding='utf-8',
                delete=False  # Don't auto-delete so caller can use the file
            )
            
            temp_file.write(xml_content)
            temp_file.close()
            
            return Path(temp_file.name)
            
        except Exception as e:
            # If any error occurs during file creation, return None
            self.logger.warning(
                "Failed to create temporary file for XBRL content.", 
                exc_info=True
            )
            return None