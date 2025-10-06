#!/usr/bin/env python3
"""
Clean navigation noise from API documentation files
"""

import os
import re
from pathlib import Path

# Directory containing API docs
DOCS_DIR = "mem0-api-docs"

# Common navigation patterns to remove
NAVIGATION_PATTERNS = [
    # Main navigation menu
    r"Mem0 home page\s*Search\.\.\.\s*⌘K\s*Documentation\s*API Reference\s*Overview\s*Memory APIs\s*.*?Changelog",
    # Footer navigation
    r"Was this page helpful\?\s*Yes\s*No\s*Suggest edits\s*Raise issue\s*Previous.*?Powered by Mintlify",
    # Social links
    r"discord\s*x\s*github\s*linkedin",
    # Duplicate headers
    r"Memory APIs\s*\n\s*(?=\w+\s+Memories)",
    r"Entities APIs\s*\n\s*(?=\w+\s+User)",
    r"Organizations APIs\s*\n\s*(?=\w+\s+Org)",
    r"Project APIs\s*\n\s*(?=\w+\s+Project)",
    r"Webhook APIs\s*\n\s*(?=\w+\s+Webhook)",
]

# Additional cleanup patterns
CLEANUP_PATTERNS = [
    # Remove "Try it" links
    r"Try it\s*\n",
    # Remove multiple empty lines
    r"\n{3,}",
    # Remove trailing whitespace
    r"[ \t]+$",
    # Clean up section headers with extra characters
    r"​\s*\n",  # Zero-width space followed by newline
]

def clean_document(content):
    """Clean navigation noise from document content"""
    
    # Apply navigation pattern removals
    for pattern in NAVIGATION_PATTERNS:
        content = re.sub(pattern, "", content, flags=re.DOTALL | re.MULTILINE)
    
    # Apply additional cleanup
    for pattern in CLEANUP_PATTERNS:
        content = re.sub(pattern, "\n" if pattern == r"\n{3,}" else "", content, flags=re.MULTILINE)
    
    # Clean up API endpoint formatting
    # Convert separated endpoint parts to single line
    content = re.sub(r"(POST|GET|PUT|DELETE|DEL)\s*\n\s*/\s*\n\s*(\w+)\s*\n\s*/\s*\n\s*(\w+)\s*\n\s*/", r"\1 /\2/\3/", content)
    content = re.sub(r"(POST|GET|PUT|DELETE|DEL)\s*\n\s*/\s*\n\s*(\w+)\s*\n\s*/", r"\1 /\2/", content)
    
    # Clean up code blocks
    content = re.sub(r"Code\s*\nOutput\s*\nCopy\s*\nAsk AI\s*\n", "```python\n", content)
    content = re.sub(r"Copy\s*\nAsk AI\s*\n", "```python\n", content)
    
    # Add proper code block endings where needed
    lines = content.split('\n')
    in_code_block = False
    cleaned_lines = []
    
    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
        
        # If we see a heading or parameter description after code, close the block
        if in_code_block and i < len(lines) - 1:
            next_line = lines[i + 1].strip()
            if (next_line and 
                (next_line.endswith('required') or 
                 next_line.endswith('optional') or
                 next_line.startswith('#') or
                 next_line in ['Authorizations', 'Query Parameters', 'Response', 'Body', 'Path Parameters'])):
                cleaned_lines.append(line)
                cleaned_lines.append('```')
                in_code_block = False
                continue
        
        cleaned_lines.append(line)
    
    # Close any unclosed code blocks
    if in_code_block:
        cleaned_lines.append('```')
    
    return '\n'.join(cleaned_lines)

def process_file(filepath):
    """Process a single documentation file"""
    print(f"Processing: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip README.md and already clean files
        if filepath.name == 'README.md' or 'get-all-memories.md' in str(filepath):
            print(f"  Skipping: {filepath.name}")
            return
        
        # Clean the content
        cleaned_content = clean_document(content)
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        print(f"  ✓ Cleaned: {filepath.name}")
        
    except Exception as e:
        print(f"  ✗ Error processing {filepath}: {str(e)}")

def main():
    """Main function to process all documentation files"""
    docs_path = Path(DOCS_DIR)
    
    if not docs_path.exists():
        print(f"Error: {DOCS_DIR} directory not found!")
        return
    
    # Get all .md files
    md_files = list(docs_path.glob("*.md"))
    
    print(f"Found {len(md_files)} documentation files")
    print("=" * 50)
    
    # Process each file
    for filepath in sorted(md_files):
        process_file(filepath)
    
    print("=" * 50)
    print("Documentation cleanup complete!")

if __name__ == "__main__":
    main()
