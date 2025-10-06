#!/usr/bin/env python3
"""
Download Mem0 documentation using Selenium for dynamic content
"""

import os
import re
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import html2text

# Base URL for Mem0 docs
BASE_URL = "https://docs.mem0.ai"

# Initialize HTML to Markdown converter
h = html2text.HTML2Text()
h.ignore_links = False
h.body_width = 0  # Don't wrap lines
h.single_line_break = True

# Directory to save docs
DOCS_DIR = "mem0-docs-complete"

# Create docs directory if it doesn't exist
os.makedirs(DOCS_DIR, exist_ok=True)

def clean_filename(filename):
    """Clean filename for safe file system use"""
    filename = re.sub(r'[<>:"/\\|?*]', '-', filename)
    filename = filename.strip('. ')
    return filename

def setup_driver():
    """Setup Chrome driver with headless option"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def wait_for_content(driver, timeout=20):
    """Wait for main content to load"""
    try:
        # Wait for the main content area to be present
        wait = WebDriverWait(driver, timeout)
        
        # Try multiple selectors
        selectors = [
            (By.CLASS_NAME, "mdx-content"),
            (By.XPATH, "//div[contains(@class, 'prose')]"),
            (By.XPATH, "//article"),
            (By.XPATH, "//main"),
            (By.XPATH, "//div[@data-page-title]")
        ]
        
        for selector_type, selector in selectors:
            try:
                element = wait.until(EC.presence_of_element_located((selector_type, selector)))
                return element
            except TimeoutException:
                continue
                
        return None
    except Exception as e:
        print(f"Error waiting for content: {e}")
        return None

def extract_api_content(driver):
    """Extract API documentation content"""
    content_dict = {}
    
    # Try to find the main content area
    main_content = wait_for_content(driver)
    
    if main_content:
        # Extract the HTML
        content_dict['html'] = main_content.get_attribute('outerHTML')
        
        # Try to extract specific API information
        try:
            # Extract title
            title_elem = driver.find_element(By.ID, "page-title")
            if title_elem:
                content_dict['title'] = title_elem.text
        except:
            pass
            
        # Try to extract code blocks
        try:
            code_blocks = driver.find_elements(By.CSS_SELECTOR, "pre code")
            content_dict['code_examples'] = [block.text for block in code_blocks]
        except:
            pass
            
        # Try to extract API endpoint info
        try:
            # Look for HTTP method badges (GET, POST, etc.)
            method_elems = driver.find_elements(By.XPATH, "//span[contains(@class, 'method') or contains(@class, 'badge')]")
            content_dict['methods'] = [elem.text for elem in method_elems if elem.text in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']]
        except:
            pass
    
    return content_dict

def save_as_markdown(url, content_dict, filename):
    """Convert content to Markdown and save"""
    markdown_content = f"""---
source: {url}
title: {content_dict.get('title', filename)}
date_downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}
---

"""
    
    # Add title if available
    if 'title' in content_dict:
        markdown_content += f"# {content_dict['title']}\n\n"
    
    # Convert main HTML content to markdown
    if 'html' in content_dict:
        main_markdown = h.handle(content_dict['html'])
        markdown_content += main_markdown
    
    # Add code examples if found separately
    if 'code_examples' in content_dict and content_dict['code_examples']:
        markdown_content += "\n\n## Code Examples\n\n"
        for i, code in enumerate(content_dict['code_examples'], 1):
            markdown_content += f"### Example {i}\n\n```\n{code}\n```\n\n"
    
    # Save to file
    filepath = os.path.join(DOCS_DIR, f"{filename}.md")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"Saved: {filepath}")

def get_all_doc_links():
    """Get all documentation links"""
    links = [
        # Main pages
        ("/", "index"),
        ("/what-is-mem0", "what-is-mem0"),
        ("/quickstart", "quickstart"),
        ("/api-reference", "api-reference-overview"),
        
        # Memory APIs
        ("/api-reference/memory/add-memories", "api-memory-add"),
        ("/api-reference/memory/get-memories", "api-memory-get"),
        ("/api-reference/memory/get-all-memories", "api-memory-get-all"),
        ("/api-reference/memory/search-memories", "api-memory-search"),
        ("/api-reference/memory/update-memory", "api-memory-update"),
        ("/api-reference/memory/delete-memory", "api-memory-delete"),
        ("/api-reference/memory/delete-all-memories", "api-memory-delete-all"),
        
        # Entity APIs
        ("/api-reference/entities/users", "api-entities-users"),
        ("/api-reference/entities/agents", "api-entities-agents"),
        ("/api-reference/entities/runs", "api-entities-runs"),
        ("/api-reference/entities/sessions", "api-entities-sessions"),
        
        # Other
        ("/integrations", "integrations"),
        ("/changelog", "changelog"),
    ]
    
    return links

def main():
    """Main function to download all docs"""
    print("Starting Mem0 documentation download with Selenium...")
    print(f"Saving to: {os.path.abspath(DOCS_DIR)}")
    
    # Setup driver
    driver = setup_driver()
    
    try:
        # Get all doc links
        doc_links = get_all_doc_links()
        
        print(f"Found {len(doc_links)} documentation pages to download")
        
        # Download each page
        for i, (path, filename) in enumerate(doc_links, 1):
            url = BASE_URL + path
            print(f"\n[{i}/{len(doc_links)}] Processing: {url}")
            
            try:
                # Navigate to page
                driver.get(url)
                
                # Wait for content to load
                time.sleep(3)  # Initial wait
                
                # Extract content
                content_dict = extract_api_content(driver)
                
                # Save as markdown
                save_as_markdown(url, content_dict, filename)
                
                # Be polite to the server
                time.sleep(1)
            
            except Exception as e:
                print(f"Error processing {url}: {e}")
                continue
        
        print(f"\nDownload complete! Documentation saved to: {os.path.abspath(DOCS_DIR)}")
        
    finally:
        # Clean up
        driver.quit()

if __name__ == "__main__":
    main()
