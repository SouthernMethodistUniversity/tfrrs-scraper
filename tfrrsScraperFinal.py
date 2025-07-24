import re
import time
import os
from urllib.parse import urljoin, quote
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import random
from playwright.sync_api import sync_playwright
from multiprocessing import freeze_support
from collections import defaultdict
from decimal import Decimal
from fake_useragent import UserAgent


EVENTS = [
    '55 Meters',
    '60 Meters',
    '100 Meters',
    '100 M',
    '200 Meters',
    '300 Meters',
    '400 Meters',
    '500 Meters',
    '800 Meters',
    '1000 Meters',
    '1500 Meters',
    'Mile',
    'Distance Medley Relay',
    '3000 Meters',
    '5000 Meters',
    '10,000 Meters',
    '2000 Steeplechase',
    '3000 Steeplechase',
    '55 Hurdles',
    '60 Hurdles',
    '100 Hurdles',
    '110 Hurdles',
    '300 Hurdles',
    '400 Hurdles',
    'Pole Vault',
    'Long Jump',
    'High Jump',
    'Triple Jump',
    '4 x 400 Relay',
    '4 x 200 Relay',
    '4 x 100 Relay',
    'Shot Put',
    'Weight Throw',
    'Discus',
    'Hammer',
    'Javelin',
    'Decathlon',
    'Heptathlon',
    'Pentathlon'
]


def setup_driver(headless=True):
    ''' 
    sets up undetected chromedriver using options/settings to make scraper more silent
    '''
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")

    options.binary_location = "~/chromium/chrome-linux/chrome"

    #options.add_argument("--no-sandbox")
    driver = uc.Chrome(options=options, version_main=140)
    driver.set_page_load_timeout(30)
    return driver

def playwright_get_html(url, wait_selector="table", timeout=25000):
    '''
    Uses Playwright to grab the html from the page, used to supply our selenium scraper
    '''
    # Initialize and grab five chrome agents from the useragent library
    ua = UserAgent()
    chrome_agents = [ua.chrome for i in range(5)]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=random.choice(chrome_agents))
            page = context.new_page()
            page.goto(url, timeout=timeout)
            page.wait_for_selector(wait_selector, timeout=timeout)
            html = page.content()
            browser.close()
            return html
    except Exception:
        return None

def selenium_html_driver(driver, url):
    '''
    Loads html content into a selenium driver via a url'''
    html = playwright_get_html(url)
    if not html:
        return False
    try:
        driver.get("data:text/html;charset=utf-8," + quote(html))
        return True
    except Exception:
        return False

def clean_time(raw_time):
    '''
    converting minute-plus times to ints'''
    time_str = raw_time.strip()
    # if times have a the form dd:dd.dd
    if re.match(r"^\d+:\d+(\.\d+)?$", time_str):
        parts = time_str.split(":")
        try:
            mins = int(parts[0])
            sec = float(parts[1])
            return round(mins * 60 + sec, 3)
        except:
            return None
    
    # remove all non digits
    time_str = re.sub(r"[^\d.]", "", time_str)
    try:
        return float(Decimal(time_str))
    except:
        return None

def mark_round(round_soup):
    '''
    finds the round the mark was made
    '''
    header = round_soup.find('h3')
    if header:
        text = header.get_text().lower()
        # Determines rund by finding identifiers in header
        if 'preliminaries' in text or 'semifinals' in text:
            return 'Prelim'
        elif 'finals' in text:
            return 'Final'
    return 'neither'

def normalize_year(raw_year):
    '''
    Normalize years as tffrs seems to be somewhat inconsistent
    '''
    raw_year = raw_year.strip()
    year_mapping = {
        "Freshman": "FR-1",
        "Sophomore": "SO-2",
        "Junior": "JR-3",
        "Senior": "SR-4"
    }
    for key, val in year_mapping.items():
        if key in raw_year:
            return val
    return raw_year.upper()

def athlete_gender(gender_soup):
    '''
    Determines if the table's event is male or female
    '''
    header = gender_soup.find('h3', string=re.compile(r'(Men|Women)', re.I))
    if header:
        text = header.get_text().lower()
        # determines gender based on men or women in header
        if 'women' in text:
            return 'Women'
        elif 'men' in text:
            return 'Men'
    return 'Unknown'

def athlete_event(event_soup):
    '''
    FInds the header inside the larger container and matches and event
    '''
    header = event_soup.find('h3')
    table = event_soup.find('table')
    if not header or not table:
        return ('Unknown', None)
    text = header.get_text().lower()
    print(f"Header text: {text}")
    for event in EVENTS:
        if event.lower() in text:
            return (event, table.get('id'))
    return ('Unknown', None)



def is_field_event(event_name):
    '''
    checks if athlete is a field athlete
    '''
    field_events = ['shot put', 'discus', 'javelin', 'hammer', 'long jump', 'triple jump', 'high jump',
     'pole vault', 'weight throw', 'heptathlon', 'decathlon', 'pentathlon']
    return any(f in event_name.lower() for f in field_events)

def parse_result_tables(table_element, is_field, round_label):
    '''
    Parses table using Selenium WebElement to capture only visible <td> values, also
    dynamically grabbing the column headers by looking at the th text
    '''
    rows = table_element.find_elements(By.TAG_NAME, "tr")[1:]
    athlete_data = []

    header_cells = [head for head in table_element.find_elements(By.TAG_NAME, "th") if  head.is_displayed()]
    col_ind = {}
    # Dynamaically grabs and assigns column indexes
    for i, th in enumerate(header_cells):
        head_text = th.text.lower()
        if 'team' in head_text:
            col_ind['team'] = i
        elif 'name' in head_text or 'athletes' in head_text:
            col_ind['athlete'] = i
        elif 'mark' in head_text or 'time' in head_text or 'points' in head_text:
            col_ind['mark'] = i
        elif 'year' in head_text or 'squad' in head_text:
            col_ind['year'] = i

    team_i = col_ind.get('team')
    athlete_i = col_ind.get('athlete')
    mark_i = col_ind.get('mark')
    year_i = col_ind.get('year')


    for row in rows:
        cols = [col for col in row.find_elements(By.TAG_NAME, "td") if col.is_displayed()]
        if len(cols) < 4:
            continue

        try:
            name_link = cols[athlete_i].find_element(By.TAG_NAME, "a") if athlete_i is not None else None
            athlete_id = name_link.get_attribute('href') if name_link else None
            name = name_link.text.strip() if name_link else None
        except:
            athlete_id = None
            name = None

         
        year = normalize_year(cols[year_i].text) if year_i is not None else None
        team = cols[team_i].text.strip() if team_i is not None else None

        text = cols[mark_i].text.strip()
        mark_val = clean_time(text)
        if not mark_val:
            continue
    
        entry = {
            'name': name,
            'year': year,
            'team': team,
            'athlete_id': athlete_id,
            'prelim': '',
            'final': '',
            'mark': mark_val
        }

        if not is_field:
            if round_label.lower().startswith('prelim'):
                entry['prelim'] = mark_val
            elif round_label.lower().startswith('final'):
                entry['final'] = mark_val

        athlete_data.append(entry)
    return athlete_data

def merge_athletes(event_name, table_pairs, is_field):
    '''
    merges and combines all entries that have the same key(Player Event) into a single entry
    '''
    event_aths = {}
    for table_element, round_label in table_pairs:
        athletes = parse_result_tables(table_element, is_field, round_label)
        for athlete in athletes:
            event_key = (athlete['athlete_id'], event_name)
            if event_key not in event_aths:
                event_aths[event_key] = athlete
            else:
                # Combining athlete rows for rounds
                existing = event_aths[key]
                if athlete['prelim']:
                    existing['prelim'] = athlete['prelim']
                if athlete['final']:
                    existing['final'] = athlete['final']
                if not is_field:
                    existing['mark'] = min(existing['mark'], athlete['mark'])
                else:
                    existing['mark'] = max(existing['mark'], athlete['mark'])
    return list(event_aths.values())

def scrape_meets(input_csv, output_csv):
    '''
    Uses Our selenium driver to go into the gendered compiled pages, then uses helpers
    to grab the athlete data and compile it
    '''
    input_df = pd.read_csv(input_csv)
    urls = input_df['original_url'].reset_index(drop=True)
    dates = input_df['DATE'].reset_index(drop=True)
    meets = input_df['MEET'].reset_index(drop=True)
    states = input_df['STATE_PROV'].reset_index(drop=True)

    all_results = []
    left_meets = []

    for idx, url in enumerate(urls):
        print(f"Processing meet {url}")
        driver = setup_driver(headless=True)

        if not selenium_html_driver(driver, url):
            print(f"Failed to load {url}")
            left_meets.append({
                'original_url': url,
                'DATE': dates[idx],
                'MEET': meets[idx],
                'STATE_PROV': states[idx]
            })
            driver.quit()
            continue

        soup = BeautifulSoup(driver.page_source, 'lxml')
        links = soup.find_all('a', href=True)

        link_data = [
            (link.text.strip(), urljoin(url, link['href']))
            for link in links
            if 'compiled' in link.text.strip().lower() 
        ]

        for link_text, compiled_url in link_data:
            print(f"Visiting {compiled_url}")
            if not selenium_html_driver(driver, compiled_url):
                print(f"Failed to load page {compiled_url}")
                time.sleep(2)
                continue

            full_soup = BeautifulSoup(driver.page_source, 'lxml')
            gender = athlete_gender(full_soup)
            table_elements = driver.find_elements(By.TAG_NAME, "table")

            event_table_map = defaultdict(list)
            # Searches for all large contianers(non section or heat tables)
            for container in full_soup.find_all('div', class_=re.compile(r'col-lg-12')):
                round_label = mark_round(container)
                print(f"Round Label {round_label}")
                event_name, table_id = athlete_event(container)
                if event_name != 'Unknown' and table_id:
                    try:
                        table_element = driver.find_element(By.ID, table_id)
                        event_table_map[event_name].append((table_element, round_label))
                    except:
                        continue

            for event_name, table_pairs in event_table_map.items():
                is_field = is_field_event(event_name)
                merged_athletes = merge_athletes(event_name, table_pairs, is_field)
                # Using a lambda function to sort based on field event or not
                sorted_aths = sorted(merged_athletes, key=lambda x: -x['mark'] if is_field else x['mark'])

                for place, athlete in enumerate(sorted_aths, 1):
                    all_results.append({
                        'Date': dates[idx],
                        'Meet': meets[idx],
                        'State': states[idx],
                        'Name': athlete['name'],
                        'Year': athlete['year'],
                        'Event': event_name,
                        'Prelim': '' if is_field else athlete.get('prelim'),
                        'Final': '' if is_field else athlete.get('final'),
                        'Best_Mark': athlete['mark'],
                        'Place': place,
                        'Gender': gender,
                        'Team': athlete['team'],
                        'Athlete_ID': athlete['athlete_id']
                    })

        driver.quit()

    pd.DataFrame(all_results).to_csv(output_csv, index=False)
    if left_meets:
        pd.DataFrame(left_meets).to_csv('remaining_meets.csv', index=False)
    else:
        if os.path.exists('remaining_meets.csv'):
            os.remove('remaining_meets.csv')
    print(f"Saved to {output_csv} with {len(all_results)} rows")

def scrape_iterator(input_csv, output_csv):
    '''
    used to catch any failed meets so no data is lost
    '''
    attempt = 0
    current_input = input_csv

    while True:
        print(f"Attempt {attempt + 1} on {current_input}")
        scrape_meets(current_input, "temp_results.csv")


        if not os.path.exists("temp_results.csv") or os.path.getsize("temp_results.csv") == 0:
            print("temp_results.csv is missing\empty")
        else:
            try:
                temp_results = pd.read_csv("temp_results.csv")

                if temp_results.empty:
                    print("temp_results.csv was read but is empty")
                else:
                    print(f"temp_results.csv read {temp_results.shape[0]} rows successfully")

                    output_columns = ['Date', 'Meet', 'State', 'Name', 'Year', 'Event',
                                    'Prelim', 'Final', 'Best_Mark', 'Place', 'Gender',
                                    'Team', 'Athlete_ID']
                    temp_results = temp_results[output_columns]

                    if os.path.exists(output_csv):
                        if os.path.getsize(output_csv) == 0:
                            os.remove(output_csv)
                            pd.DataFrame(columns=output_columns).to_csv(output_csv, index=False)
                        existing = pd.read_csv(output_csv)
                        
                    else:
                        existing = pd.DataFrame(columns=output_columns)

                    combined = pd.concat([existing, temp_results], ignore_index=True).drop_duplicates()
                    combined.to_csv(output_csv, index=False)
                    print(f"appended {len(temp_results)} new results")
            
            except pd.errors.EmptyDataError:
                print("the path exists but has no header or rows")
            except Exception as e:
                print(f"Error reading temp_results.csv, {e}")

        try:
            remaining = pd.read_csv("remaining_meets.csv")
        except FileNotFoundError:
            print("No remaining_meets.csv, all done")
            break

        remaining.drop_duplicates().to_csv("retry_input.csv", index=False)
        current_input = "retry_input.csv"
        attempt += 1

        print("Cooling down")
        time.sleep(180)


full_df = pd.read_csv("gendered_meets_01102025.csv")
full_df = full_df[::2]
full_df.to_csv('adj.csv', index=False)
trial_df = full_df[7000:7002]
trial_df.to_csv('trial_run.csv', index=False)

scrape_iterator("trial_run.csv", "trial_results.csv")