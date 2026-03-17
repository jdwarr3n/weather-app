import os
import requests
import tkinter as tk
from tkinter import ttk, messagebox


def get_coordinates(zip_code):
    """
    Uses the free Nominatim (OpenStreetMap) API to get latitude and longitude.
    This doesn't require an API key, just a respectful User-Agent!
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "postalcode": zip_code,
        "country": "USA",
        "format": "json"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data:
            # Return the first match's latitude and longitude
            return float(data[0]['lat']), float(data[0]['lon'])
        else:
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to geocoding service: {e}")
        return None, None

def get_emoji(condition):
    """
    Returns an emoji based on the short forecast condition.
    """
    condition = condition.lower()
    if 'sunny' in condition or 'clear' in condition:
        return '☀️'
    elif 'snow' in condition:
        return '❄️'
    elif 'storm' in condition or 'thunder' in condition:
        return '⛈️'
    elif 'rain' in condition or 'shower' in condition:
        return '🌧️'
    elif 'cloud' in condition:
        if 'partly' in condition or 'mostly' in condition:
            return '⛅'
        return '☁️'
    elif 'fog' in condition:
        return '🌫️'
    elif 'wind' in condition:
        return '💨'
    else:
        return '🌡️' # Default

def get_nws_weather(lat, lon):
    """
    Uses the National Weather Service API to get current temp and forecast.
    """
    headers = {"User-Agent": "SimplePythonWeatherApp/1.0 (student@example.com)"}
    
    # Step 1: Get the Gridpoint (tells us which specific NWS office handles this location)
    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    
    try:
        points_resp = requests.get(points_url, headers=headers)
        points_resp.raise_for_status()
        points_data = points_resp.json()
        
        # Get the specific URLs for the daily and hourly forecasts for this grid
        forecast_url = points_data['properties']['forecast']
        hourly_url = points_data['properties']['forecastHourly']
        
        # Step 2: Get Current Temperature from the Hourly Forecast
        hourly_resp = requests.get(hourly_url, headers=headers)
        hourly_resp.raise_for_status()
        hourly_data = hourly_resp.json()
        
        current_period = hourly_data['properties']['periods'][0]
        current_temp = current_period['temperature']
        current_unit = current_period['temperatureUnit']
        current_condition = current_period['shortForecast']
        icon = get_emoji(current_condition)
        
        # Step 3: Get Highs and Lows from the Daily Forecast
        forecast_resp = requests.get(forecast_url, headers=headers)
        forecast_resp.raise_for_status()
        forecast_data = forecast_resp.json()
        
        daily_periods = forecast_data['properties']['periods']
        
        # Figure out the high and low based on time of day for "Today"
        today_high = "N/A"
        today_low = "N/A"
        
        # We need to collect the next 3 distinct days' forecast
        forecast_3day = []
        current_day_name = daily_periods[0]['name']
        is_tonight_start = not daily_periods[0]['isDaytime']
        
        # Helper to format a day's forecast
        def make_day_data(day_name, high, low, condition):
            return {
                "name": day_name,
                "high": f"{high}°" if high != "N/A" else "N/A",
                "low": f"{low}°" if low != "N/A" else "N/A",
                "condition": condition
            }
            
        # Parse today's high/low specifically
        if len(daily_periods) >= 2:
            if is_tonight_start:
                # Tonight
                today_low = daily_periods[0]['temperature']
                # Start collecting future days from index 1 (Tomorrow)
                start_idx = 1
            else:
                # Today
                today_high = daily_periods[0]['temperature']
                today_low = daily_periods[1]['temperature']
                # Start collecting future days from index 2 (Tomorrow)
                start_idx = 2

        # Extract next 3 days
        i = start_idx
        days_collected = 0
        while i < len(daily_periods) and days_collected < 3:
            p = daily_periods[i]
            if p['isDaytime']:
                day_name = p['name'][:3] # Shorten name, e.g., 'Tuesday' -> 'Tue'
                high = p['temperature']
                condition = p['shortForecast']
                
                # Try to get the low from the next period if it exists
                low = "N/A"
                if i + 1 < len(daily_periods):
                     next_p = daily_periods[i+1]
                     if not next_p['isDaytime']: # Double check it's the night period
                         low = next_p['temperature']
                
                forecast_3day.append(make_day_data(day_name, high, low, condition))
                days_collected += 1
                i += 2 # Skip the night period we just processed
            else:
                # Occurs if we hit a weird sequence, try moving to next
                i += 1

        # Step 4: Extract 32-hour Hourly Forecast
        hourly_periods = hourly_data['properties']['periods'][:32]
        forecast_hourly = []
        for p in hourly_periods:
            time_obj = p['startTime'].split('T')[1][:5] # Get HH:MM
            # Convert 24h to 12h format
            hour = int(time_obj.split(':')[0])
            ampm = "A" if hour < 12 else "P"
            display_hour = hour % 12
            if display_hour == 0: display_hour = 12
            
            forecast_hourly.append({
                "time": f"{display_hour}{ampm}",
                "temp": f"{p['temperature']}°",
                "rain": f"{p['probabilityOfPrecipitation'].get('value', 0)}%",
                "wind": f"{p['windSpeed']} {p['windDirection']}",
                "summary": p['shortForecast'],
                "raw_temp": p['temperature'],
                "raw_rain": p['probabilityOfPrecipitation'].get('value') if p['probabilityOfPrecipitation'].get('value') is not None else 0
            })

        # Get the specific location name (City, State)
        location_name = f"{points_data['properties']['relativeLocation']['properties']['city']}, {points_data['properties']['relativeLocation']['properties']['state']}"

        return {
            "location": location_name,
            # We strip the unit because "72°F" becomes just "72" or "72°"
            "temp": str(current_temp) + "°",
            "condition": current_condition,
            "icon": icon,
            "high": f"{today_high}°{current_unit}" if today_high != "N/A" else "N/A",
            "low": f"{today_low}°{current_unit}" if today_low != "N/A" else "N/A",
            "forecast_3day": forecast_3day,
            "forecast_hourly": forecast_hourly
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to National Weather Service: {e}")
        return None
    except KeyError as e:
        print(f"Error parsing NWS data: {e}")
        return None

class WeatherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Weather App")
        self.root.configure(bg="#f0f0f0")

        
        # --- Top Input Frame ---
        input_frame = tk.Frame(self.root, bg="#f0f0f0", pady=10)
        input_frame.pack(fill=tk.X)
        
        # Name Input
        tk.Label(input_frame, text="Name:", bg="#f0f0f0", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=(20, 5))
        self.name_entry = ttk.Entry(input_frame, width=12, font=("Helvetica", 12))
        self.name_entry.pack(side=tk.LEFT, padx=5)
        self.name_entry.bind('<Return>', lambda event: self.zip_entry.focus())

        # Zip Input
        tk.Label(input_frame, text="Zip:", bg="#f0f0f0", font=("Helvetica", 12)).pack(side=tk.LEFT, padx=(20, 5))
        
        self.zip_entry = ttk.Entry(input_frame, width=5, font=("Helvetica", 12))
        self.zip_entry.pack(side=tk.LEFT, padx=5)
        self.zip_entry.bind('<Return>', lambda event: self.add_weather_card())
        
        # --- Bottom Cards Frame (Notebook/Tabs) ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.added_zips = [] # Keep track of what we've added to avoid duplicates. Stores (zip, name, frame)
        self.save_file = "saved_zips.txt"
        self.load_saved_zips()

    def load_saved_zips(self):
        if os.path.exists(self.save_file):
            with open(self.save_file, "r") as f:
                lines = f.read().splitlines()
            for line in lines:
                if line.strip():
                    parts = line.strip().split(',', 1)
                    if len(parts) == 2:
                        self.process_zip(parts[0].strip(), parts[1].strip(), is_initial_load=True)
                    else:
                        self.process_zip(line.strip(), "", is_initial_load=True)

    def save_zips(self):
        with open(self.save_file, "w") as f:
            for zip_data in self.added_zips:
                # added_zips contains tuples: (zip_code, custom_name, card_frame)
                f.write(f"{zip_data[0]},{zip_data[1]}\n")

    def add_weather_card(self):
        zip_code = self.zip_entry.get().strip()
        custom_name = self.name_entry.get().strip()
        
        if not zip_code:
            return
            
        success = self.process_zip(zip_code, custom_name)
        if success:
            self.save_zips()
        self.reset_entry()

    def process_zip(self, zip_code, custom_name, is_initial_load=False):
        # Check if zip already exists
        if any(z[0] == zip_code for z in self.added_zips):
            if not is_initial_load:
                messagebox.showinfo("Duplicate", "You've already added this zip code.")
            return False

        if not is_initial_load:
            # Disable button while fetching
            self.zip_entry.config(state='disabled')
            self.name_entry.config(state='disabled')
            self.root.update()

        lat, lon = get_coordinates(zip_code)
        
        if lat is None or lon is None:
            if not is_initial_load:
                messagebox.showerror("Error", f"Could not find coordinates for Zip Code: {zip_code}")
            return False
            
        weather_data = get_nws_weather(lat, lon)
        
        if weather_data is None:
            if not is_initial_load:
                messagebox.showerror("Error", "Could not fetch weather data from NWS.")
            return False
            
        self.create_card_ui(zip_code, custom_name, weather_data)
        return True

    def reset_entry(self):
        self.zip_entry.config(state='normal')
        self.name_entry.config(state='normal')
        self.zip_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.name_entry.focus()

    def remove_card(self, card_frame, zip_code):
        self.notebook.forget(card_frame)
        card_frame.destroy()
        
        # Remove tuple from data list and re-save
        self.added_zips = [z for z in self.added_zips if z[0] != zip_code]
        self.save_zips()

    def toggle_forecast(self, state_dict, daily_frame, hourly_frame, toggle_btn, current_weather_frame, main_container):
        if state_dict["mode"] == "D":
            state_dict["mode"] = "H"
            current_weather_frame.pack_forget()
            daily_frame.pack_forget()
            hourly_frame.pack(anchor="center")
            toggle_btn.config(text="D")
        else:
            state_dict["mode"] = "D"
            hourly_frame.pack_forget()
            current_weather_frame.pack(fill=tk.X, before=main_container)
            daily_frame.pack(anchor="center")
            toggle_btn.config(text="H")

    def create_card_ui(self, zip_code, custom_name, data):
        # Tab Label uses custom name if provided, otherwise the zip code
        tab_base = custom_name if custom_name else zip_code
        tab_name = (tab_base[:6] + '..') if len(tab_base) > 8 else tab_base
        
        # Card Title uses custom name if provided, otherwise the city/state
        display_name = custom_name if custom_name else data['location']
        
        # Card Container (acts as the Tab content)
        card = tk.Frame(self.notebook, bg="white", bd=2, relief=tk.GROOVE, padx=15, pady=15)
        
        # Add to Notebook
        self.notebook.add(card, text=tab_name)
        # Select the newly added tab
        self.notebook.select(card)
        
        # Keep track for deletion/saving
        self.added_zips.append((zip_code, custom_name, card))
        
        # Header Container for Buttons
        header_frame = tk.Frame(card, bg="white")
        header_frame.pack(fill=tk.X)

        # Toggle Button (Top Left)
        toggle_frame = tk.Frame(header_frame, bg="white")
        toggle_frame.pack(side=tk.LEFT)
        
        state_dict = {"mode": "D"}
        toggle_btn = tk.Button(toggle_frame, text="H", bg="#e0e0e0", relief=tk.RAISED, width=2, font=("Helvetica", 10, "bold"))
        toggle_btn.pack(side=tk.LEFT)

        # Close Button (Top Right)
        close_btn = tk.Button(header_frame, text="✕", fg="gray", bg="white", bd=0, font=("Helvetica", 14, "bold"), 
                               command=lambda: self.remove_card(card, zip_code))
        close_btn.pack(side=tk.RIGHT)

        # Location Name
        tk.Label(card, text=display_name, bg="white", font=("Helvetica", 16, "bold"), wraplength=350, justify="center").pack(pady=(5, 2))
        
        # Subtext Line (City/State and Zip)
        if custom_name:
            subtext = f"{data['location']} • {zip_code}"
        else:
            subtext = f"{zip_code}"
            
        tk.Label(card, text=subtext, bg="white", fg="gray", font=("Helvetica", 11)).pack(pady=(0, 15))

        # Current Weather info (to hide in hourly view)
        current_weather_frame = tk.Frame(card, bg="white")
        current_weather_frame.pack(fill=tk.X)

        # Temp and Icon Container (to ensure absolute centering)
        center_container = tk.Frame(current_weather_frame, bg="white")
        center_container.pack(fill=tk.X, pady=(10, 5))
        
        # An inner frame that we center, which holds both the temp and icon
        temp_frame = tk.Frame(center_container, bg="white")
        temp_frame.pack(anchor="center") 
        
        # Icon label - using ttk.Label as it handles modern system font/emoji bounds better
        style = ttk.Style()
        style.configure("White.TLabel", background="white")
        ttk.Label(temp_frame, text=data['icon'], font=("Helvetica", 36), style="White.TLabel").pack(side=tk.LEFT, padx=(0, 5))

        # Temp label
        tk.Label(temp_frame, text=data['temp'], bg="white", font=("Helvetica", 36, "bold")).pack(side=tk.LEFT)
        
        # Current Condition (Centered)
        tk.Label(current_weather_frame, text=data['condition'], bg="white", font=("Helvetica", 12)).pack(pady=(5, 0))
        
        # Separator Line
        ttk.Separator(current_weather_frame, orient='horizontal').pack(fill=tk.X, pady=15)

        # Forecast Containers
        main_forecast_container = tk.Frame(card, bg="white")
        main_forecast_container.pack(fill=tk.BOTH, expand=True)

        # 3-Day Forecast Section (Daily)
        daily_frame = tk.Frame(main_forecast_container, bg="white")
        daily_frame.pack(anchor="center")
        
        # Configure columns for grid
        daily_frame.columnconfigure(0, weight=1, minsize=60)  # Day
        daily_frame.columnconfigure(1, minsize=40)  # Icon
        daily_frame.columnconfigure(2, minsize=80)  # High
        daily_frame.columnconfigure(3, minsize=80)  # Low
        
        # Create forecast rows
        for row_idx, day in enumerate(data.get('forecast_3day', [])):
            # Day name
            tk.Label(daily_frame, text=day['name'], bg="white", font=("Helvetica", 12, "bold"), anchor="w").grid(row=row_idx, column=0, sticky="w", pady=4)
            
            # Icon
            icon = get_emoji(day['condition'])
            tk.Label(daily_frame, text=icon, bg="white", font=("Helvetica", 14)).grid(row=row_idx, column=1, padx=5, pady=4)
            
            # High
            high_frame = tk.Frame(daily_frame, bg="white")
            high_frame.grid(row=row_idx, column=2, sticky="e", padx=(10, 5))
            tk.Label(high_frame, text="H:", bg="white", fg="#D32F2F", font=("Helvetica", 11, "bold")).pack(side=tk.LEFT)
            tk.Label(high_frame, text=day['high'], bg="white", font=("Helvetica", 11, "bold")).pack(side=tk.LEFT, padx=(2,0))
            
            # Low
            low_frame = tk.Frame(daily_frame, bg="white")
            low_frame.grid(row=row_idx, column=3, sticky="e", padx=(5, 0))
            tk.Label(low_frame, text="L:", bg="white", fg="#1976D2", font=("Helvetica", 11, "bold")).pack(side=tk.LEFT)
            tk.Label(low_frame, text=day['low'], bg="white", font=("Helvetica", 11, "bold")).pack(side=tk.LEFT, padx=(2,0))

        # Hourly Forecast Section (Hidden by default)
        hourly_frame = tk.Frame(main_forecast_container, bg="white")

        # Configure 8 columns for the hourly grid to fit 32 hours
        for c in range(8):
            hourly_frame.columnconfigure(c, weight=1)

        # Create 4 rows x 8 columns grid for 32 hours
        # We need to make sure we extract 32 hours back on line 154 if we want 32 here, 
        # but the API usually returns 156 hours so we just need to slice up to 32.
        hourly_data = data.get('forecast_hourly', [])[:32]
        
        # Calculate max and min temps for the 32-hour slice
        raw_temps = [d['raw_temp'] for d in hourly_data]
        max_temp = max(raw_temps)
        min_temp = min(raw_temps)
        
        for idx, h_data in enumerate(hourly_data):
            # Calculate row, leaving spaces for separators
            # Rows 0, 2, 4, 6 will be data. Rows 1, 3, 5 will be separators.
            r = (idx // 8) * 2
            c = idx % 8
            
            # Create a small frame for this hour's time and temp
            cell_frame = tk.Frame(hourly_frame, bg="white")
            cell_frame.grid(row=r, column=c, padx=0, pady=1) # Minimal pad
            
            # Time (e.g. 1P, 2A) - slightly bigger
            tk.Label(cell_frame, text=h_data['time'], bg="white", fg="#555555", font=("Helvetica", 11)).pack(pady=0)
            
            # Determine color for temp
            temp_color = "black"
            if h_data['raw_temp'] == max_temp:
                temp_color = "#D32F2F" # Red
            elif h_data['raw_temp'] == min_temp:
                temp_color = "#1976D2" # Blue
                
            # Temp (e.g. 72°) - slightly bigger
            tk.Label(cell_frame, text=h_data['temp'], bg="white", fg=temp_color, font=("Helvetica", 12, "bold")).pack(pady=0)
            
            # Add a separator below this row if we're at the end of a row (and not the last row)
            if c == 7 and r < 6:
                sep = ttk.Separator(hourly_frame, orient="horizontal")
                sep.grid(row=r+1, column=0, columnspan=8, sticky="ew", pady=2)

        # Set button command for toggling
        toggle_btn.config(command=lambda: self.toggle_forecast(state_dict, daily_frame, hourly_frame, toggle_btn, current_weather_frame, main_forecast_container))


def main():
    root = tk.Tk()
    app = WeatherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
