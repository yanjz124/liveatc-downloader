import argparse
import sys

parser = argparse.ArgumentParser()

commands = parser.add_subparsers(title='command', dest='command')

parser_stations = commands.add_parser('stations', help='List stations for a given airport')
parser_stations.add_argument('icao', help='Airport ICAO code, e.g. KPDX')

parser_download = commands.add_parser('download', help='Download MP3 archive for a given station')
parser_download.add_argument('station', help='Station identifier, e.g. kpdx_app')
parser_download.add_argument('-d', '--date', help='Archive date, e.g. Oct-01-2021 defaults to current date (LiveATC only saves archives for 30 days)')
parser_download.add_argument('-t', '--time', help='Archive Zulu time, e.g. 0000Z, defaults to current time')

parser_download_range = commands.add_parser('download-range', help='Download MP3 archives for a date/time range')
parser_download_range.add_argument('station', help='Station identifier, e.g. kpdx_app')
parser_download_range.add_argument('start', help='Start date and time, e.g. Dec-10-2025-0000Z')
parser_download_range.add_argument('-e', '--end', help='End date and time, e.g. Dec-11-2025-1500Z (defaults to now)')
parser_download_range.add_argument('-d', '--delay', type=float, default=10.0, help='Delay in seconds between downloads to avoid rate-limiting (default: 10)')



def get_args():
  return parser.parse_args(sys.argv[1:])
