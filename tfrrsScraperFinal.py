import re
import time
import os
from urllib.parse import urljoin, quote
import pandas as pd
from bs4 import BeautifulSoup
from collections import defaultdict
from decimal import Decimal
import pickle
import requests


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

SCRATCH = "/lustre/scratch/client/users/mlangstonsmith/tfrrs_partials"
os.makedirs(SCRATCH, exist_ok=True)

def get_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    return BeautifulSoup(response.text, 'lxml')

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

def parse_result_tables(table, is_field, round_label):
    athlete_data = []
    header_cells = table.find_all('th')
    col_ind = {}

    for i, th in enumerate(header_cells):
        head_text = th.get_text().lower()
        if 'team' in head_text:
            col_ind['team'] = i
        elif 'name' in head_text or 'athlete' in head_text:
            col_ind['athlete'] = i
        elif 'mark' in head_text or 'time' in head_text or 'points' in head_text:
            col_ind['mark'] = i
        elif 'year' in head_text or 'squad' in head_text:
            col_ind['year'] = i

    for row in table.find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) < 4:
            continue

        try:
            name_link = cols[col_ind['athlete']].find('a') if 'athlete' in col_ind else None
            athlete_id = name_link['href'] if name_link else None
            name = name_link.get_text(strip=True) if name_link else cols[col_ind['athlete']].get_text(strip=True)
        except:
            name = None
            athlete_id = None

        year = normalize_year(cols[col_ind['year']].get_text()) if 'year' in col_ind else None
        team = cols[col_ind['team']].get_text(strip=True) if 'team' in col_ind else None
        mark_val = clean_time(cols[col_ind['mark']].get_text()) if 'mark' in col_ind else None
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
                existing = event_aths[event_key]
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
    input_df = pd.read_csv(input_csv)
    urls = input_df['original_url'].reset_index(drop=True)
    dates = input_df['DATE'].reset_index(drop=True)
    meets = input_df['MEET'].reset_index(drop=True)
    states = input_df['STATE_PROV'].reset_index(drop=True)

    all_results = []
    left_meets = []

    for idx, url in enumerate(urls):
        time.sleep(2)
        print(f"Processing meet {url} -- {idx}/{len(urls)}")

        page_soup = get_html(url)
        if not page_soup:
            print(f"[ERROR] Could not load meet page: {url}")
            left_meets.append({
                'original_url': url,
                'DATE': dates[idx],
                'MEET': meets[idx],
                'STATE_PROV': states[idx]
            })
            continue

        compiled_links = [
            urljoin(url, a['href']) for a in page_soup.find_all('a', href=True)
            if 'compiled' in a.text.strip().lower()
        ]

        for compiled_url in compiled_links:
            print(f"Visiting compiled: {compiled_url}")
            compiled_soup = get_html(compiled_url)
            if not compiled_soup:
                print(f"[WARN] Skipping compiled URL: {compiled_url}")
                continue

            gender = athlete_gender(compiled_soup)
            event_table_map = defaultdict(list)

            for container in compiled_soup.find_all('div', class_=re.compile(r'col-lg-12')):
                round_label = mark_round(container)
                event_name, table_id = athlete_event(container)
                if event_name != 'Unknown':
                    table = container.find('table', id=table_id) if table_id else container.find('table')
                    if table:
                        event_table_map[event_name].append((table, round_label))

            for event_name, table_pairs in event_table_map.items():
                is_field = is_field_event(event_name)
                merged_athletes = merge_athletes(event_name, table_pairs, is_field)
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

        with open(f'{SCRATCH}/{idx}_partial.pkl', 'wb') as f:
            pickle.dump(all_results, f)

    pd.DataFrame(all_results).to_csv(output_csv, index=False)
    if left_meets:
        pd.DataFrame(left_meets).to_csv('remaining_meets.csv', index=False)
    else:
        if os.path.exists('remaining_meets.csv'):
            os.remove('remaining_meets.csv')

    print(f"[✓] Saved to {output_csv} with {len(all_results)} rows")

def scrape_iterator(input_csv, output_csv):
    '''
    used to catch any failed meets so no data is lost
    '''
    attempt = 0
    current_input = input_csv

    while True:
        
        print(f"Attempt {attempt + 1} on {current_input}")
        
        scrape_meets(current_input, output_csv)


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
        time.sleep(20)


#full_df = pd.read_csv("gendered_meets_01102025.csv")
#full_df = full_df[::2]
#full_df.to_csv('adj.csv', index=False)
#trial_df = full_df[6970:7002]
#trial_df.to_csv('trial_run.csv', index=False)

scrape_meets("gendered_meets_01102025.csv", "results.csv")