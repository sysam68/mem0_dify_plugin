#!/usr/bin/env python3
"""
Download Mem0 documentation and save as Markdown files
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import html2text

# Base URL for Mem0 docs
BASE_URL = "https://docs.mem0.ai"

# Initialize HTML to Markdown converter
h = html2text.HTML2Text()
h.ignore_links = False
h.body_width = 0  # Don't wrap lines
h.single_line_break = True

# Directory to save docs
DOCS_DIR = "mem0-docs"

# Create docs directory if it doesn't exist
os.makedirs(DOCS_DIR, exist_ok=True)

# Headers to mimic browser request
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_filename(filename):
    """Clean filename for safe file system use"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '-', filename)
    filename = filename.strip('. ')
    return filename

def get_page_content(url):
    """Fetch and parse page content"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_main_content(html_content):
    """Extract main content from HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try to find main content area (adjust selectors based on actual structure)
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    
    if not main_content:
        # Fallback: try to find content by common class names
        for class_name in ['mdx-content', 'prose', 'documentation', 'content-area']:
            main_content = soup.find('div', class_=re.compile(class_name))
            if main_content:
                break
    
    if main_content:
        # Remove script and style tags
        for script in main_content(['script', 'style']):
            script.decompose()
        
        return str(main_content)
    
    return html_content

def save_as_markdown(url, content, filename):
    """Convert HTML to Markdown and save"""
    # Extract main content
    main_html = extract_main_content(content)
    
    # Convert to Markdown
    markdown_content = h.handle(main_html)
    
    # Add metadata header
    metadata = f"""---
source: {url}
title: {filename}
date_downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}
---

"""
    
    # Save to file
    filepath = os.path.join(DOCS_DIR, f"{filename}.md")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(metadata + markdown_content)
    
    print(f"Saved: {filepath}")

def get_all_doc_links(base_url):
    """Get all documentation links from the site"""
    links = set()
    
    # Start with main documentation pages
    main_pages = [
        "/",
        "/what-is-mem0",
        "/quickstart",
        "/api-reference",
        "/api-reference/memory/add-memories",
        "/api-reference/memory/get-memories",
        "/api-reference/memory/get-all-memories",
        "/api-reference/memory/search-memories",
        "/api-reference/memory/update-memory",
        "/api-reference/memory/delete-memory",
        "/api-reference/memory/delete-all-memories",
        "/api-reference/entities/users",
        "/api-reference/entities/agents",
        "/api-reference/entities/runs",
        "/api-reference/entities/sessions",
        "/integrations",
        "/changelog",
    ]
    
    for page in main_pages:
        full_url = urljoin(base_url, page)
        links.add(full_url)
    
    return links

def main():
    """Main function to download all docs"""
    print(f"Starting Mem0 documentation download...")
    print(f"Saving to: {os.path.abspath(DOCS_DIR)}")
    
    # Get all doc links
    doc_links = get_all_doc_links(BASE_URL)
    
    print(f"Found {len(doc_links)} documentation pages to download")
    
    # Download each page
    for i, url in enumerate(doc_links, 1):
        print(f"\n[{i}/{len(doc_links)}] Processing: {url}")
        
        # Get page content
        content = get_page_content(url)
        if not content:
            continue
        
        # Generate filename from URL
        path = urlparse(url).path.strip('/')
        if not path:
            filename = "index"
        else:
            filename = clean_filename(path.replace('/', '-'))
        
        # Save as markdown
        save_as_markdown(url, content, filename)
        
        # Be polite to the server
        time.sleep(1)
    
    print(f"\nDownload complete! Documentation saved to: {os.path.abspath(DOCS_DIR)}")
    
    # Create an index file
    create_index_file(doc_links)

def create_index_file(links):
    """Create an index file with all downloaded documents"""
    index_content = """# Mem0 Documentation Index

This is an index of all downloaded Mem0 documentation pages.

## Pages

"""
    
    for url in sorted(links):
        path = urlparse(url).path.strip('/')
        if not path:
            filename = "index"
            title = "Home"
        else:
            filename = clean_filename(path.replace('/', '-'))
            title = path.replace('-', ' ').replace('/', ' > ').title()
        
        index_content += f"- [{title}]({filename}.md) - [Source]({url})\n"
    
    with open(os.path.join(DOCS_DIR, "INDEX.md"), 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"Created index file: {os.path.join(DOCS_DIR, 'INDEX.md')}")

if __name__ == "__main__":
    main()
