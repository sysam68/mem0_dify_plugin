#!/usr/bin/env python3
"""
Fetch Mem0 API documentation using browser automation
to handle client-side rendered content
"""

import os
import time
import json
from datetime import datetime

# Try to use playwright, fallback to selenium if not available
try:
    from playwright.sync_api import sync_playwright
    USE_PLAYWRIGHT = True
except ImportError:
    USE_PLAYWRIGHT = False
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("Please install either playwright or selenium:")
        print("pip install playwright && playwright install")
        print("OR")
        print("pip install selenium")
        exit(1)

# URLs to fetch from sitemap
URLS_TO_FETCH = [
    ("https://docs.mem0.ai/api-reference/memory/v2-get-memories", "v2-get-memories.md"),
    ("https://docs.mem0.ai/api-reference/memory/v2-search-memories", "v2-search-memories.md"),
    ("https://docs.mem0.ai/api-reference/memory/add-memories", "add-memories.md"),
    ("https://docs.mem0.ai/api-reference/memory/update-memory", "update-memory.md"),
    ("https://docs.mem0.ai/api-reference/memory/delete-memory", "delete-memory.md"),
    ("https://docs.mem0.ai/api-reference/memory/delete-memories", "delete-memories.md"),
    ("https://docs.mem0.ai/api-reference/memory/create-memory-export", "create-memory-export.md"),
    ("https://docs.mem0.ai/api-reference/memory/get-memory-export", "get-memory-export.md"),
    ("https://docs.mem0.ai/api-reference/entities/get-users", "get-users.md"),
    ("https://docs.mem0.ai/api-reference/entities/delete-user", "delete-user.md"),
    ("https://docs.mem0.ai/api-reference/organization/create-org", "create-org.md"),
    ("https://docs.mem0.ai/api-reference/organization/get-orgs", "get-orgs.md"),
    ("https://docs.mem0.ai/api-reference/organization/get-org", "get-org.md"),
    ("https://docs.mem0.ai/api-reference/organization/get-org-members", "get-org-members.md"),
    ("https://docs.mem0.ai/api-reference/project/get-projects", "get-projects.md"),
    ("https://docs.mem0.ai/api-reference/webhook/get-webhook", "get-webhook.md"),
]

OUTPUT_DIR = "mem0-api-docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_with_playwright(url):
    """Fetch content using Playwright"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Loading {url}...")
        try:
            # Increase timeout and wait for DOM content loaded instead of networkidle
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for content to load with specific selectors
            try:
                # Wait for API content to appear
                page.wait_for_selector('[data-testid="api-content"], .api-reference-content, main', timeout=10000)
            except:
                # If specific selectors don't exist, just wait a bit
                page.wait_for_timeout(5000)
            
            # Try to find the main content area
            content = ""
            
            # Try multiple strategies to get content
            selectors = [
                '[data-testid="api-content"]',
                '.api-reference-content', 
                'article',
                'main',
                '.documentation-content', 
                '.api-content', 
                '[role="main"]',
                '.content',
                '#content',
                'body'
            ]
            
            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        text_content = element.inner_text()
                        if text_content and len(text_content) > 100:  # Make sure we got meaningful content
                            content = text_content
                            break
                except:
                    continue
            
            # If still no content, get the full page
            if not content:
                content = page.content()
                
        except Exception as e:
            print(f"Error loading page: {str(e)}")
            content = f"Error: {str(e)}"
        finally:
            browser.close()
            
        return content

def fetch_with_selenium(url):
    """Fetch content using Selenium"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"Loading {url}...")
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional wait for dynamic content
        time.sleep(3)
        
        # Try to find main content
        content = ""
        
        # Try different selectors
        selectors = ['main', '.documentation-content', '.api-content', '[role="main"]', 'body']
        
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.text:
                    content = element.text
                    break
            except:
                continue
        
        # If no content found, get full page source
        if not content:
            content = driver.page_source
        
        return content
        
    finally:
        driver.quit()

def extract_api_info(content, url):
    """Extract API information from the fetched content"""
    # This is a simple extraction, might need adjustment based on actual content structure
    doc = {
        "source": url,
        "title": url.split('/')[-1].replace('-', ' ').title(),
        "date_created": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "content": content
    }
    
    return doc

def save_documentation(doc, filename):
    """Save documentation to markdown file"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    md_content = f"""---
source: {doc['source']}
title: {doc['title']}
date_created: {doc['date_created']}
---

# {doc['title']}

{doc['content']}
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"Saved: {filepath}")

def main():
    """Main function to fetch all documentation"""
    print(f"Using {'Playwright' if USE_PLAYWRIGHT else 'Selenium'} for browser automation")
    print(f"Fetching {len(URLS_TO_FETCH)} API documentation pages...\n")
    
    for url, filename in URLS_TO_FETCH:
        try:
            # Fetch content
            if USE_PLAYWRIGHT:
                content = fetch_with_playwright(url)
            else:
                content = fetch_with_selenium(url)
            
            # Extract API information
            doc = extract_api_info(content, url)
            
            # Save documentation
            save_documentation(doc, filename)
            
            # Small delay to be respectful
            time.sleep(1)
            
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            continue
    
    print(f"\nDocumentation fetching complete! Files saved in: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main()
