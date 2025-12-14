#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from liveatc import get_stations, download_archive
import os
import time

try:
    from tkcalendar import DateEntry
    HAVE_CALENDAR = True
except ImportError:
    HAVE_CALENDAR = False


class LiveATCDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LiveATC Downloader")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        self.stations_data = []
        self.selected_station = None  # Track selected station persistently
        self.downloading = False
        self.download_cancelled = False

        self.create_widgets()
        
    def create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # ===== AIRPORT SEARCH =====
        row = 0
        ttk.Label(main_frame, text="Airport ICAO Code:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=(0, 5))
        
        row += 1
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        search_frame.columnconfigure(0, weight=1)
        
        self.icao_entry = ttk.Entry(search_frame, font=('Arial', 10))
        self.icao_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.icao_entry.bind('<Return>', lambda e: self.search_stations())
        
        self.search_btn = ttk.Button(search_frame, text="Search Stations", command=self.search_stations)
        self.search_btn.grid(row=0, column=1)
        
        # ===== STATIONS LIST =====
        row += 1
        ttk.Label(main_frame, text="Available Stations:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=(10, 5))
        
        row += 1
        # Frame for listbox and scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Listbox
        self.stations_listbox = tk.Listbox(list_frame, height=8, font=('Courier', 9),
                                           yscrollcommand=scrollbar.set)
        self.stations_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.stations_listbox.yview)
        self.stations_listbox.bind('<<ListboxSelect>>', self.on_station_select)
        
        # ===== SELECTED STATION INFO =====
        row += 1
        ttk.Label(main_frame, text="Selected Station:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=(10, 5))
        
        row += 1
        self.station_info_label = ttk.Label(main_frame, text="No station selected", 
                                           foreground='gray', wraplength=700)
        self.station_info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # ===== TIME RANGE =====
        row += 1
        ttk.Label(main_frame, text="Time Range (UTC/Zulu):", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=(10, 5))
        
        row += 1
        time_frame = ttk.Frame(main_frame)
        time_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        from datetime import timezone
        current_time = datetime.now(timezone.utc)

        # Start time
        ttk.Label(time_frame, text="Start:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

        if HAVE_CALENDAR:
            # Use calendar date picker with arrow key navigation
            self.start_date_entry = DateEntry(time_frame, width=15, background='darkblue',
                                             foreground='white', borderwidth=2,
                                             date_pattern='mm-dd-y')
            self.start_date_entry.set_date(current_time)
        else:
            # Fallback to text entry
            self.start_date_entry = ttk.Entry(time_frame, width=15)
            self.start_date_entry.insert(0, current_time.strftime('%b-%d-%Y'))
        self.start_date_entry.grid(row=0, column=1, padx=(0, 5))

        # Start time - Hour spinbox (00-23)
        self.start_hour = tk.Spinbox(time_frame, from_=0, to=23, width=4, format="%02.0f",
                                     wrap=True, state='readonly', readonlybackground='white',
                                     buttonbackground='lightgray')
        self.start_hour.grid(row=0, column=2, padx=(0, 2))
        self.start_hour.delete(0, tk.END)
        self.start_hour.insert(0, '00')

        # Start time - Minute spinbox (00 or 30 only)
        self.start_minute = tk.Spinbox(time_frame, values=['00', '30'], width=4,
                                       wrap=True, state='readonly', readonlybackground='white',
                                       buttonbackground='lightgray')
        self.start_minute.grid(row=0, column=3, padx=(0, 2))
        self.start_minute.delete(0, tk.END)
        self.start_minute.insert(0, '00')

        ttk.Label(time_frame, text="Z").grid(row=0, column=4, sticky=tk.W, padx=(0, 15))

        # End time
        ttk.Label(time_frame, text="End:").grid(row=0, column=5, sticky=tk.W, padx=(0, 5))

        if HAVE_CALENDAR:
            # Use calendar date picker with arrow key navigation
            self.end_date_entry = DateEntry(time_frame, width=15, background='darkblue',
                                           foreground='white', borderwidth=2,
                                           date_pattern='mm-dd-y')
            self.end_date_entry.set_date(current_time)
        else:
            # Fallback to text entry
            self.end_date_entry = ttk.Entry(time_frame, width=15)
            self.end_date_entry.insert(0, current_time.strftime('%b-%d-%Y'))
        self.end_date_entry.grid(row=0, column=6, padx=(0, 5))

        # End time - Hour spinbox (00-23)
        minutes = (current_time.minute // 30) * 30
        rounded_time = current_time.replace(minute=minutes, second=0, microsecond=0)
        self.end_hour = tk.Spinbox(time_frame, from_=0, to=23, width=4, format="%02.0f",
                                   wrap=True, state='readonly', readonlybackground='white',
                                   buttonbackground='lightgray')
        self.end_hour.grid(row=0, column=7, padx=(0, 2))
        self.end_hour.delete(0, tk.END)
        self.end_hour.insert(0, f"{rounded_time.hour:02d}")

        # End time - Minute spinbox (00 or 30 only)
        self.end_minute = tk.Spinbox(time_frame, values=['00', '30'], width=4,
                                     wrap=True, state='readonly', readonlybackground='white',
                                     buttonbackground='lightgray')
        self.end_minute.grid(row=0, column=8, padx=(0, 2))
        self.end_minute.delete(0, tk.END)
        self.end_minute.insert(0, f"{rounded_time.minute:02d}")

        ttk.Label(time_frame, text="Z").grid(row=0, column=9, sticky=tk.W)

        # Format help
        row += 1
        help_text = "Click date to open calendar | Click spinbox arrows to adjust time | Time is in UTC/Zulu" if HAVE_CALENDAR else "Date format: Dec-11-2025 | Click spinbox arrows to adjust time | Time is in UTC/Zulu"
        ttk.Label(main_frame, text=help_text,
                 foreground='gray', font=('Arial', 8)).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # ===== OUTPUT FOLDER =====
        row += 1
        ttk.Label(main_frame, text="Output Folder:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=(10, 5))
        
        row += 1
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        
        self.output_entry = ttk.Entry(output_frame, font=('Arial', 9))
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.output_entry.insert(0, os.path.expanduser('~/Downloads'))

        self.browse_btn = ttk.Button(output_frame, text="Browse...", command=self.browse_output)
        self.browse_btn.grid(row=0, column=1)

        # ===== DOWNLOAD SETTINGS =====
        row += 1
        settings_frame = ttk.Frame(main_frame)
        settings_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 10))

        # Thread count
        ttk.Label(settings_frame, text="Concurrent downloads:", font=('Arial', 9)).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))

        self.thread_count = tk.Spinbox(settings_frame, from_=1, to=10, width=4,
                                       wrap=True, state='readonly', readonlybackground='white',
                                       buttonbackground='lightgray')
        self.thread_count.grid(row=0, column=1, padx=(0, 5))
        self.thread_count.delete(0, tk.END)
        self.thread_count.insert(0, '3')

        ttk.Label(settings_frame, text="threads", font=('Arial', 9)).grid(
            row=0, column=2, sticky=tk.W, padx=(0, 15))

        # Delay between downloads
        ttk.Label(settings_frame, text="Delay between downloads:", font=('Arial', 9)).grid(
            row=0, column=3, sticky=tk.W, padx=(0, 5))

        self.delay_entry = ttk.Entry(settings_frame, width=8)
        self.delay_entry.grid(row=0, column=4, padx=(0, 5))
        self.delay_entry.insert(0, '2')

        ttk.Label(settings_frame, text="seconds (per thread, to avoid rate-limiting)",
                 foreground='gray', font=('Arial', 8)).grid(row=0, column=5, sticky=tk.W)
        
        # ===== DOWNLOAD BUTTONS =====
        row += 1
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=(10, 10))
        
        self.download_btn = ttk.Button(button_frame, text="Download Archives", 
                                       command=self.start_download, state='disabled')
        self.download_btn.grid(row=0, column=0, padx=(0, 5))
        
        self.cancel_btn = ttk.Button(button_frame, text="Stop Download", 
                                     command=self.cancel_download, state='disabled')
        self.cancel_btn.grid(row=0, column=1)
        
        # ===== PROGRESS LOG =====
        row += 1
        ttk.Label(main_frame, text="Download Log:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=(10, 5))
        
        row += 1
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, font=('Courier', 9),
                                                   state='disabled')
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ===== STATUS BAR =====
        row += 1
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
    def log(self, message):
        """Add message to log window"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        
    def set_status(self, message):
        """Update status bar"""
        self.status_label.config(text=message)
        
    def search_stations(self):
        """Search for stations by ICAO code"""
        icao = self.icao_entry.get().strip().upper()
        if not icao:
            messagebox.showwarning("Input Required", "Please enter an airport ICAO code")
            return
        
        self.set_status(f"Searching for stations at {icao}...")
        self.search_btn.config(state='disabled')
        self.stations_listbox.delete(0, tk.END)
        self.stations_data = []
        self.selected_station = None  # Clear selected station on new search
        self.station_info_label.config(text="No station selected", foreground='gray')
        self.download_btn.config(state='disabled')
        
        # Run search in background thread
        thread = threading.Thread(target=self._search_stations_thread, args=(icao,))
        thread.daemon = True
        thread.start()
        
    def _search_stations_thread(self, icao):
        """Background thread for station search"""
        try:
            stations = list(get_stations(icao))
            self.stations_data = stations
            
            # Update UI in main thread
            self.root.after(0, self._update_stations_list, stations)
        except Exception as e:
            self.root.after(0, self._search_error, str(e))
            
    def _update_stations_list(self, stations):
        """Update stations listbox with results"""
        self.stations_listbox.delete(0, tk.END)
        
        if not stations:
            self.stations_listbox.insert(tk.END, "No stations found")
            self.set_status("No stations found")
        else:
            for station in stations:
                status = "●" if station['up'] else "○"
                display = f"{status} [{station['identifier']}] - {station['title']}"
                self.stations_listbox.insert(tk.END, display)
            self.set_status(f"Found {len(stations)} station(s)")
            
        self.search_btn.config(state='normal')
        
    def _search_error(self, error):
        """Handle search error"""
        messagebox.showerror("Search Error", f"Failed to search stations:\n{error}")
        self.set_status("Search failed")
        self.search_btn.config(state='normal')
        
    def on_station_select(self, event):
        """Handle station selection"""
        selection = self.stations_listbox.curselection()
        if not selection or not self.stations_data:
            return

        idx = selection[0]
        if idx >= len(self.stations_data):
            return

        station = self.stations_data[idx]

        # Store selected station persistently
        self.selected_station = station

        # Display station info
        freqs = ", ".join([f"{f['title']} ({f['frequency']})" for f in station['frequencies']])
        status = "ONLINE" if station['up'] else "OFFLINE"
        info = f"ID: {station['identifier']}\nStatus: {status}\nFrequencies: {freqs}"

        self.station_info_label.config(text=info, foreground='black')
        self.download_btn.config(state='normal' if station['up'] else 'disabled')
        
    def browse_output(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(initialdir=self.output_entry.get())
        if folder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, folder)
            
    def cancel_download(self):
        """Cancel ongoing download"""
        if self.downloading:
            self.download_cancelled = True
            self.log("Download cancelled by user")
            self.set_status("Cancelling download...")
            self.cancel_btn.config(state='disabled')
    
    def start_download(self):
        """Start download process"""
        # Validate inputs - use persistently stored station instead of current listbox selection
        if not self.selected_station:
            messagebox.showwarning("No Selection", "Please select a station")
            return

        station = self.selected_station

        # Get dates - handle both DateEntry and regular Entry widgets
        if HAVE_CALENDAR:
            start_date = self.start_date_entry.get_date().strftime('%b-%d-%Y')
            end_date = self.end_date_entry.get_date().strftime('%b-%d-%Y')
        else:
            start_date = self.start_date_entry.get().strip()
            end_date = self.end_date_entry.get().strip()

        start_time = f"{self.start_hour.get()}{self.start_minute.get()}Z"
        end_time = f"{self.end_hour.get()}{self.end_minute.get()}Z"
        output_folder = self.output_entry.get().strip()
        delay_str = self.delay_entry.get().strip()
        thread_count_str = self.thread_count.get().strip()

        if not all([start_date, end_date, output_folder, delay_str, thread_count_str]):
            messagebox.showwarning("Input Required", "Please fill in all fields")
            return

        # Validate delay
        try:
            delay = float(delay_str)
            if delay < 0:
                messagebox.showwarning("Invalid Delay", "Delay must be a positive number")
                return
        except ValueError:
            messagebox.showwarning("Invalid Delay", "Delay must be a number (e.g., 2)")
            return

        # Validate thread count
        try:
            num_threads = int(thread_count_str)
            if num_threads < 1 or num_threads > 10:
                messagebox.showwarning("Invalid Thread Count", "Thread count must be between 1 and 10")
                return
        except ValueError:
            messagebox.showwarning("Invalid Thread Count", "Thread count must be a number")
            return
        
        # Validate output folder
        if not os.path.exists(output_folder):
            try:
                os.makedirs(output_folder)
            except Exception as e:
                messagebox.showerror("Folder Error", f"Cannot create output folder:\n{e}")
                return
        
        # Parse dates
        try:
            start_datetime = datetime.strptime(f"{start_date}-{start_time}", '%b-%d-%Y-%H%MZ')
            end_datetime = datetime.strptime(f"{end_date}-{end_time}", '%b-%d-%Y-%H%MZ')
            
            if end_datetime <= start_datetime:
                messagebox.showwarning("Invalid Range", "End time must be after start time")
                return
        except ValueError as e:
            messagebox.showerror("Date Format Error", 
                               f"Invalid date/time format:\n{e}\n\nUse format: Dec-11-2025 and 1430Z")
            return
        
        # Clear log
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        
        # Disable controls
        self.download_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.search_btn.config(state='disabled')
        self.downloading = True
        self.download_cancelled = False
        
        # Start download in background
        thread = threading.Thread(target=self._download_thread,
                                 args=(station, start_datetime, end_datetime, output_folder, delay, num_threads))
        thread.daemon = True
        thread.start()
        
    def _download_thread(self, station, start_datetime, end_datetime, output_folder, delay, num_threads):
        """Background thread for downloading with multithreading support"""
        import shutil

        # Generate list of all time intervals to download
        intervals = []
        current = start_datetime
        while current <= end_datetime:
            intervals.append(current)
            current += timedelta(minutes=30)

        total_intervals = len(intervals)
        downloaded = 0
        failed = 0

        self.root.after(0, self.log, f"Starting download for {station['identifier']}")
        self.root.after(0, self.log, f"Time range: {start_datetime} to {end_datetime} UTC")
        self.root.after(0, self.log, f"Total intervals: {total_intervals}")
        self.root.after(0, self.log, f"Output folder: {output_folder}")
        self.root.after(0, self.log, f"Using {num_threads} concurrent thread(s)")
        self.root.after(0, self.log, f"Delay between downloads: {delay} seconds (per thread)\n")

        def download_single_interval(interval_time):
            """Download a single time interval"""
            if self.download_cancelled:
                return None

            date_str = interval_time.strftime('%b-%d-%Y')
            time_str = interval_time.strftime('%H%MZ')

            try:
                # Download to temp location first
                filepath = download_archive(station['identifier'], date_str, time_str)

                # Move to output folder
                filename = os.path.basename(filepath)
                dest_path = os.path.join(output_folder, filename)
                shutil.move(filepath, dest_path)

                return {'success': True, 'date': date_str, 'time': time_str, 'filename': filename}
            except Exception as e:
                error_msg = str(e)
                if len(error_msg) > 100:
                    error_msg = error_msg[:100] + "..."
                return {'success': False, 'date': date_str, 'time': time_str, 'error': error_msg}

        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit all download tasks
            futures = []
            for idx, interval in enumerate(intervals):
                if self.download_cancelled:
                    break
                future = executor.submit(download_single_interval, interval)
                futures.append((future, idx + 1, interval))

                # Add delay between submissions to stagger the threads
                if delay > 0 and idx < len(intervals) - 1:
                    time.sleep(delay / num_threads)

            # Process results as they complete
            for future, idx, interval in futures:
                if self.download_cancelled:
                    # Cancel remaining futures
                    future.cancel()
                    continue

                try:
                    result = future.result()
                    if result is None:
                        # Task was cancelled
                        continue

                    progress = f"[{idx}/{total_intervals}]"

                    if result['success']:
                        downloaded += 1
                        self.root.after(0, self.log,
                                      f"{progress} [OK] {result['date']} {result['time']} -> {result['filename']}")
                        self.root.after(0, self.set_status,
                                      f"Progress: {downloaded + failed}/{total_intervals} ({downloaded} OK, {failed} failed)")
                    else:
                        failed += 1
                        self.root.after(0, self.log,
                                      f"{progress} [FAIL] {result['date']} {result['time']}: {result['error']}")
                        self.root.after(0, self.set_status,
                                      f"Progress: {downloaded + failed}/{total_intervals} ({downloaded} OK, {failed} failed)")
                except Exception as e:
                    failed += 1
                    self.root.after(0, self.log, f"[{idx}/{total_intervals}] [ERROR] Unexpected error: {str(e)}")

        # Summary
        if not self.download_cancelled:
            self.root.after(0, self.log, f"\n=== Download Complete ===")
        else:
            self.root.after(0, self.log, f"\n=== Download Stopped ===")
        self.root.after(0, self.log, f"Successfully downloaded: {downloaded} files")
        self.root.after(0, self.log, f"Failed: {failed} files")

        # Re-enable controls
        self.root.after(0, self._download_complete, downloaded, failed)
        
    def _download_complete(self, downloaded, failed):
        """Handle download completion"""
        self.download_btn.config(state='normal')
        self.cancel_btn.config(state='disabled')
        self.search_btn.config(state='normal')
        self.downloading = False
        
        if self.download_cancelled:
            self.set_status(f"Download stopped: {downloaded} successful, {failed} failed")
        else:
            self.set_status(f"Download complete: {downloaded} successful, {failed} failed")
        
        if downloaded > 0 and not self.download_cancelled:
            messagebox.showinfo("Download Complete", 
                              f"Downloaded {downloaded} file(s)\nFailed: {failed}\n\n"
                              f"Files saved to:\n{self.output_entry.get()}")
        elif downloaded > 0 and self.download_cancelled:
            messagebox.showinfo("Download Stopped", 
                              f"Download cancelled.\n\nDownloaded {downloaded} file(s) before stopping\nFailed: {failed}\n\n"
                              f"Files saved to:\n{self.output_entry.get()}")


def main():
    root = tk.Tk()
    app = LiveATCDownloaderGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
