"""
CSE Dividend Announcements Scraper
This script scrapes dividend announcements from the CSE blog and filters by month.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from collections import defaultdict
import pandas as pd

def get_blogspot_page(url):
    """Fetch a blogspot page"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers)
    return BeautifulSoup(response.content, 'html.parser')

def extract_dividend_data(post):
    """Extract dividend information from a blog post"""
    data = {}
    
    # Get the title which contains the date and company
    title_elem = post.find(['h3', 'h2'])
    if not title_elem:
        return None
    
    title_link = title_elem.find('a')
    if not title_link:
        return None
    
    title = title_link.get_text()
    
    # Extract date from title (format: DD-MMM-YYYY)
    date_match = re.search(r'(\d{2}-[A-Za-z]{3}-\d{4})', title)
    if not date_match:
        return None
    
    data['Post_Date'] = date_match.group(1)
    
    # Extract company code from title
    code_match = re.search(r'-\s+([A-Z]+)\s*$', title)
    if code_match:
        data['Company_Code'] = code_match.group(1)
    
    # Get the post content
    content = post.get_text()
    
    # Extract company name (first line after the title usually)
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    if len(lines) > 1:
        data['Company_Name'] = lines[1]
    
    # Extract Date of Announcement
    ann_date_match = re.search(r'Date of (?:Initial )?Announcement:\s*-?\s*(\d{2}-[A-Za-z]{3}-\d{4})', content)
    if ann_date_match:
        data['Date_of_Announcement'] = ann_date_match.group(1)
    
    # Extract XD Date
    xd_match = re.search(r'XD:\s*-?\s*(\d{2}\.[A-Za-z]{3}\.\d{4})', content)
    if xd_match:
        data['XD_Date'] = xd_match.group(1).replace('.', '-')
    elif re.search(r'XD:\s*-?\s*TBA', content):
        data['XD_Date'] = 'TBA'
    
    # Extract Financial Year
    fy_match = re.search(r'Financial Year:\s*-?\s*([\d\s/]+)', content)
    if fy_match:
        data['Financial_Year'] = fy_match.group(1).strip()
    
    # Extract Dividend Rate
    rate_match = re.search(r'Rate of Dividend:\s*-?\s*Rs\.\s*([\d.]+)\s*per share', content)
    if rate_match:
        data['Dividend_Rate'] = f"Rs. {rate_match.group(1)}"
    
    return data

def scrape_dividend_announcements(num_years=5):
    """Scrape dividend announcements from the blog"""
    base_url = "https://cse-dividend-announcements.blogspot.com/"
    all_dividends = []
    
    print(f"Scraping dividend announcements for the past {num_years} years...")
    print("This may take a few minutes...\n")
    
    # Calculate the cutoff date
    current_year = datetime.now().year
    cutoff_year = current_year - num_years
    
    # Start with the main page
    page_urls = [base_url]
    visited = set()
    
    # We'll scrape multiple pages by following pagination
    page_count = 0
    max_pages = num_years * 20  # Estimate based on posting frequency
    
    while page_urls and page_count < max_pages:
        url = page_urls.pop(0)
        if url in visited:
            continue
        
        visited.add(url)
        page_count += 1
        
        try:
            soup = get_blogspot_page(url)
            
            # Find all blog posts
            posts = soup.find_all('div', class_='post-outer')
            
            if not posts:
                # Try alternative structure
                posts = soup.find_all(['div', 'article'], class_=re.compile('post|entry'))
            
            for post in posts:
                dividend_data = extract_dividend_data(post)
                if dividend_data and 'Date_of_Announcement' in dividend_data:
                    # Check if within year range
                    try:
                        ann_date = datetime.strptime(dividend_data['Date_of_Announcement'], '%d-%b-%Y')
                        if ann_date.year >= cutoff_year:
                            all_dividends.append(dividend_data)
                        elif ann_date.year < cutoff_year:
                            # We've gone far enough back
                            page_urls.clear()
                            break
                    except:
                        pass
            
            # Find "Older Posts" link for pagination
            older_link = soup.find('a', class_='blog-pager-older-link')
            if older_link and older_link.get('href'):
                next_url = older_link['href']
                if next_url not in visited:
                    page_urls.append(next_url)
            
            if page_count % 5 == 0:
                print(f"Scraped {page_count} pages, found {len(all_dividends)} announcements so far...")
                
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue
    
    print(f"\nTotal announcements found: {len(all_dividends)}")
    return all_dividends

def filter_by_month(dividends, month_number):
    """Filter dividends by announcement month"""
    filtered = []
    
    for div in dividends:
        if 'Date_of_Announcement' in div:
            try:
                ann_date = datetime.strptime(div['Date_of_Announcement'], '%d-%b-%Y')
                if ann_date.month == month_number:
                    filtered.append(div)
            except:
                pass
    
    return filtered

def display_results(dividends):
    """Display the filtered results in a nice format"""
    if not dividends:
        print("No announcements found for the selected month.")
        return
    
    # Convert to DataFrame for better display
    df = pd.DataFrame(dividends)
    
    # Select and order columns
    columns = ['Company_Name', 'Company_Code', 'Date_of_Announcement', 
               'XD_Date', 'Financial_Year', 'Dividend_Rate']
    
    # Only include columns that exist
    display_cols = [col for col in columns if col in df.columns]
    df_display = df[display_cols]
    
    # Sort by announcement date
    if 'Date_of_Announcement' in df_display.columns:
        df_display['sort_date'] = pd.to_datetime(df_display['Date_of_Announcement'], 
                                                   format='%d-%b-%Y', errors='coerce')
        df_display = df_display.sort_values('sort_date', ascending=False)
        df_display = df_display.drop('sort_date', axis=1)
    
    print(f"\n{'='*100}")
    print(f"Found {len(dividends)} dividend announcements")
    print(f"{'='*100}\n")
    
    # Display as a formatted table
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)
    
    print(df_display.to_string(index=False))
    print(f"\n{'='*100}\n")
    
    return df_display

def main():
    """Main function to run the scraper"""
    print("CSE Dividend Announcements Scraper")
    print("=" * 50)
    
    # Get number of years
    while True:
        try:
            years_input = input("\nHow many years back do you want to search? (default: 5): ").strip()
            num_years = int(years_input) if years_input else 5
            if num_years > 0:
                break
            else:
                print("Please enter a positive number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    # Get month number
    while True:
        try:
            month_input = input("\nEnter the month number (1-12): ").strip()
            month_number = int(month_input)
            if 1 <= month_number <= 12:
                break
            else:
                print("Please enter a number between 1 and 12.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    print(f"\nSearching for dividends announced in {month_names[month_number-1]} "
          f"over the past {num_years} years...")
    
    # Scrape the data
    all_dividends = scrape_dividend_announcements(num_years)
    
    # Filter by month
    filtered_dividends = filter_by_month(all_dividends, month_number)
    
    # Display results
    df = display_results(filtered_dividends)
    
    # Offer to save to CSV
    if filtered_dividends:
        save = input("\nWould you like to save these results to a CSV file? (y/n): ").strip().lower()
        if save == 'y':
            filename = f"cse_dividends_{month_names[month_number-1].lower()}_{num_years}years.csv"
            df.to_csv(filename, index=False)
            print(f"\nResults saved to {filename}")

if __name__ == "__main__":
    main()
