import re
import os

import requests
from bs4 import BeautifulSoup


def get_stations(icao):
  # Try with default SSL verification first, fallback to unverified if it fails
  try:
    page = requests.get(f'https://www.liveatc.net/search/?icao={icao}', timeout=10)
  except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
    # If SSL verification fails, retry without verification (less secure but works)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    page = requests.get(f'https://www.liveatc.net/search/?icao={icao}', verify=False, timeout=10)
  
  soup = BeautifulSoup(page.content, 'html.parser')

  stations = soup.find_all('table', class_='body', border='0', padding=lambda x: x != '0')
  freqs = soup.find_all('table', class_='freqTable', colspan='2')

  for table, freqs in zip(stations, freqs):
    title = table.find('strong').text
    up = table.find('font').text == 'UP'
    href = table.find('a', href=lambda x: x and x.startswith('/archive.php')).attrs['href']

    identifier = re.findall(r'/archive.php\?m=([a-zA-Z0-9_]+)', href)[0]

    frequencies = []
    rows = freqs.find_all('tr')[1:]
    for row in rows:
      cols = row.find_all('td')
      freq_title = cols[0].text
      freq_frequency = cols[1].text

      frequencies.append({'title': freq_title, 'frequency': freq_frequency})

    yield {'identifier': identifier, 'title': title, 'frequencies': frequencies, 'up': up}


def download_archive(station, date, time):
  # Try with default SSL verification first, fallback to unverified if it fails
  try:
    page = requests.get(f'https://www.liveatc.net/archive.php?m={station}', timeout=10)
  except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
    # If SSL verification fails, retry without verification (less secure but works)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    page = requests.get(f'https://www.liveatc.net/archive.php?m={station}', verify=False, timeout=10)
  
  soup = BeautifulSoup(page.content, 'html.parser')
  archive_identifer = soup.find('option', selected=True).attrs['value']

  # Extract airport code from station identifier (e.g., 'kcho3_zdc_121675' -> 'kcho')
  # Remove trailing digits from the first part of the station identifier
  station_prefix = station.split('_')[0]
  airport_code = re.sub(r'\d+$', '', station_prefix)
  
  # https://archive.liveatc.net/kpdx/KPDX-App-Dep-Oct-01-2021-0000Z.mp3
  filename = f'{archive_identifer}-{date}-{time}.mp3'

  path = f'/tmp/{filename}'
  url = f'https://archive.liveatc.net/{airport_code}/{filename}'
  
  import time as time_module
  import subprocess
  import sys

  # Retry logic with exponential backoff
  max_retries = 3
  for attempt in range(max_retries):
    try:
      print(f"Downloading: {url}")

      # Try using curl first (works better with archive.liveatc.net)
      try:
        # Use curl if available - it handles archive.liveatc.net better than Python requests
        result = subprocess.run(
          ['curl', '-f', '-L', '--max-time', '30', '-o', path, url],
          capture_output=True,
          text=True,
          timeout=35
        )
        if result.returncode == 0:
          return path
        else:
          # curl failed, try requests as fallback
          raise Exception(f"curl failed: {result.stderr}")
      except (FileNotFoundError, Exception) as curl_error:
        # curl not available or failed, use requests library
        print(f"  Trying Python requests (curl unavailable/failed)...")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Try without SSL verification since archive.liveatc.net has issues
        response = requests.get(url, timeout=30, stream=True, verify=False)
        response.raise_for_status()

        # Write the file in chunks
        with open(path, 'wb') as f:
          for chunk in response.iter_content(chunk_size=8192):
            if chunk:
              f.write(chunk)
        return path

    except (subprocess.TimeoutExpired, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
      if attempt < max_retries - 1:
        wait_time = 2 ** attempt  # 1, 2, 4 seconds
        print(f"  Timeout/Connection error, retrying in {wait_time}s...")
        time_module.sleep(wait_time)
      else:
        raise Exception(f"Failed after {max_retries} attempts: {e}")
    except (requests.exceptions.HTTPError, Exception) as e:
      # HTTP errors (like 403, 404) or other errors, don't retry
      if "404" in str(e) or "403" in str(e):
        raise
      elif attempt < max_retries - 1:
        wait_time = 2 ** attempt
        print(f"  Error: {e}, retrying in {wait_time}s...")
        time_module.sleep(wait_time)
      else:
        raise


# download_archive('kpdx_zse', 'Oct-01-2021', '0000Z')
