import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

def setup_driver():
    """Sets up the Edge WebDriver using the local executable."""
    edge_options = Options()
    edge_options.add_argument("--headless") 
    edge_options.add_argument("--ignore-certificate-errors")
    edge_options.add_argument("--ignore-ssl-errors")
    edge_options.add_argument("--allow-running-insecure-content")
    edge_options.add_argument("--disable-gpu")
    edge_options.add_argument("--no-sandbox")
    edge_options.add_argument("--disable-dev-shm-usage")
    edge_options.add_argument("--window-size=1920,1080")
    
    try:
        # Ensure msedgedriver.exe is in the same folder as this script
        service = Service(executable_path=os.path.join(os.getcwd(), "crawler\msedgedriver.exe"))
        driver = webdriver.Edge(service=service, options=edge_options)
    except Exception as e:
        print(f"Error setting up driver: {e}")
        print("Please ensure msedgedriver.exe is in the same folder.")
        return None

    return driver

def scrape_fd_rates():
    base_url = "https://scripbox.com/fixed-deposit"
    
    driver = setup_driver()
    if not driver:
        return

    try:
        for year in range(1, 11):
            tenure_days = year * 365
            print(f"\n--- Processing data for {year} year(s) ({tenure_days} days) ---")
            
            page = 1
            all_dataframes = []
            
            while True:
                url = f"{base_url}?tenure={tenure_days}&sortBy=interest_rate&page={page}"
                print(f"  Scraping Page {page}...")
                
                driver.get(url)
                
                # 1. Wait for the table to be present
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table"))
                    )
                except:
                    print(f"    Timeout waiting for table on Page {page}. Stopping.")
                    break
                
                # 2. Extract Data with Retry Logic
                df = None
                try:
                    time.sleep(2) # Buffer for JS rendering
                    tables = pd.read_html(driver.page_source)
                    
                    if tables:
                        # Pick the largest table (usually the main data)
                        df = max(tables, key=lambda x: len(x))
                        # Clean columns
                        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                except Exception as e:
                    print(f"    Error parsing table on Page {page}: {e}")
                    print(f"    Retrying once...")
                    time.sleep(3)
                    try:
                        tables = pd.read_html(driver.page_source)
                        if tables:
                            df = max(tables, key=lambda x: len(x))
                            df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                    except:
                        print(f"    Retry failed. Skipping Page {page}.")
                        break

                # 3. Validation
                if df is None or df.empty:
                    print(f"    No data found on Page {page}. Stopping pagination.")
                    break
                
                # Check for duplicates (if we accidentally loop back)
                if all_dataframes:
                    # Compare first row of current page with first row of first page
                    if df.iloc[0, 0] == all_dataframes[0].iloc[0, 0]:
                        print(f"    Detected duplicate start row. End of list.")
                        break

                all_dataframes.append(df)
                print(f"    Successfully scraped {len(df)} rows.")

                # 4. Pagination Check (UPDATED WITH YOUR SPECIFIC XPATH)
                try:
                    # Use the exact XPath provided
                    next_btn_xpath = '//*[@id="__next"]/div/section[2]/div/div/div[2]/div/div[3]/a'
                    next_element = driver.find_element(By.XPATH, next_btn_xpath)
                    
                    # Check if the element is "disabled" (common on last pages)
                    # We inspect the class attribute
                    class_attr = next_element.get_attribute("class") or ""
                    
                    # Logic: If the button exists but has 'disabled' in its class, we stop.
                    # Otherwise, we assume it leads to the next page.
                    if "disabled" in class_attr.lower():
                        print(f"    Next button found but is disabled. Last page reached.")
                        break
                    else:
                        # Button exists and is active -> Go to next page
                        page += 1
                        time.sleep(1) # Be polite to server
                        
                except:
                    # If we can't find the element at all, we assume we are on the last page
                    # (Because on the last page, the 'Next' button usually disappears)
                    print(f"    Next button (XPath) not found. Assuming end of list.")
                    break

            # Save CSV for this year
            if all_dataframes:
                final_df = pd.concat(all_dataframes, ignore_index=True)
                filename = f"Data\\fd_rates_{year}_year.csv"
                final_df.to_csv(filename, index=False)
                print(f"  >> Saved {len(final_df)} total rows to {filename}")
            else:
                print(f"  >> No data saved for {year} year(s).")

    finally:
        driver.quit()
        print("\nAll tasks completed.")

if __name__ == "__main__":
    scrape_fd_rates()