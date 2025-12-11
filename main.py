#!/usr/bin/env python3

from cli import get_args
from liveatc import get_stations, download_archive
from datetime import datetime, timedelta

# Gets the last Zulu period of 30 minutes
# E.g. if time is 10:35:00, it will return 10:00:00
def get_last_zulu_period(date, minutes=30):
  return date - timedelta(minutes=minutes) - (date - datetime.min) % timedelta(minutes=minutes)


def stations(args):
  stations = get_stations(args.icao)
  for station in stations:
    print(f"[{station['identifier']}] - {station['title']}")

    for freq in station['frequencies']:
      print(f"\t{freq['title']} - {freq['frequency']}")

    print()


def download(args):
  from datetime import timezone
  date_now = datetime.now(timezone.utc).replace(tzinfo=None)

  last_period = get_last_zulu_period(date_now)

  if not args.date and not args.time:
    date = last_period.strftime('%b-%d-%Y')
    time = last_period.strftime('%H%MZ')
  else:
    date = args.date if args.date else date_now.strftime('%b-%d-%Y')
    time = args.time if args.time else last_period.strftime('%H%MZ')

  download_archive(args.station, date, time)


def download_range(args):
  """Download archives for a date/time range"""
  import time

  # Parse start and end times
  start_date = datetime.strptime(args.start, '%b-%d-%Y-%H%MZ')

  if args.end:
    end_date = datetime.strptime(args.end, '%b-%d-%Y-%H%MZ')
  else:
    from datetime import timezone
    end_date = datetime.now(timezone.utc).replace(tzinfo=None)

  current = start_date
  downloaded_files = []
  failed_files = []
  delay = args.delay if hasattr(args, 'delay') else 10.0

  print(f"Downloading archives from {start_date} to {end_date}")
  print(f"Station: {args.station}")
  print(f"Delay between downloads: {delay} seconds\n")

  # Download in 30-minute intervals
  while current <= end_date:
    date_str = current.strftime('%b-%d-%Y')
    time_str = current.strftime('%H%MZ')

    try:
      filepath = download_archive(args.station, date_str, time_str)
      downloaded_files.append(filepath)
      print(f"[OK] Downloaded {date_str} {time_str}")

      # Add delay after successful download (except for the last one)
      if current + timedelta(minutes=30) <= end_date and delay > 0:
        print(f"  Waiting {delay}s before next download...")
        time.sleep(delay)
    except Exception as e:
      error_msg = str(e)
      failed_files.append((f"{date_str} {time_str}", error_msg))
      print(f"[FAIL] Failed to download {date_str} {time_str}: {error_msg}")

    current += timedelta(minutes=30)
  
  print(f"\n=== Summary ===")
  print(f"Successfully downloaded: {len(downloaded_files)} files")
  print(f"Failed: {len(failed_files)} files")
  
  if failed_files and len(failed_files) <= 10:
    print(f"\nFailed downloads:")
    for time_period, error in failed_files[:10]:
      print(f"  {time_period}: {error}")
  
  return downloaded_files


if __name__ == '__main__':
  args = get_args()
  print(args)

  if args.command == 'stations':
    stations(args)
  elif args.command == 'download':
    download(args)
  elif args.command == 'download-range':
    download_range(args)
