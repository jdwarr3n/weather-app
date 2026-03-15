/**
 * Weather App Logic
 * Fetches data from Nominatim and NWS APIs
 * Persists data to localStorage
 */

const STORAGE_KEY = 'weather_app_data';

// --- State Management ---
let state = {
    locations: [], // [{ zip, name, weatherData }]
    activeZip: null
};

// --- API Functions ---

async function getCoordinates(zip) {
    const url = `https://nominatim.openstreetmap.org/search?postalcode=${zip}&country=USA&format=json`;
    try {
        const response = await fetch(url, {
            headers: { 'User-Agent': 'WeatherAppWeb/1.0 (student@example.com)' }
        });
        const data = await response.json();
        if (data && data.length > 0) {
            return { lat: data[0].lat, lon: data[0].lon };
        }
    } catch (e) {
        console.error("Geocoding error:", e);
    }
    return null;
}

function getEmoji(condition) {
    condition = condition.toLowerCase();
    if (condition.includes('sunny') || condition.includes('clear')) return '☀️';
    if (condition.includes('snow')) return '❄️';
    if (condition.includes('storm') || condition.includes('thunder')) return '⛈️';
    if (condition.includes('rain') || condition.includes('shower')) return '🌧️';
    if (condition.includes('cloud')) {
        if (condition.includes('partly') || condition.includes('mostly')) return '⛅';
        return '☁️';
    }
    if (condition.includes('fog')) return '🌫️';
    if (condition.includes('wind')) return '💨';
    return '🌡️';
}

async function getWeatherData(lat, lon) {
    try {
        const pointsUrl = `https://api.weather.gov/points/${lat},${lon}`;
        const pointsResp = await fetch(pointsUrl);
        const pointsData = await pointsResp.json();

        const forecastUrl = pointsData.properties.forecast;
        const hourlyUrl = pointsData.properties.forecastHourly;

        const [hourlyResp, forecastResp] = await Promise.all([
            fetch(hourlyUrl),
            fetch(forecastUrl)
        ]);

        const hourlyData = await hourlyResp.json();
        const forecastData = await forecastResp.json();

        const current = hourlyData.properties.periods[0];
        const daily = forecastData.properties.periods;

        let todayHigh = "N/A", todayLow = "N/A";
        const forecast3Day = [];

        // Parse today and future days
        if (daily.length >= 2) {
            if (daily[0].isDaytime) {
                todayHigh = daily[0].temperature;
                todayLow = daily[1].temperature;
                parseForecast(daily.slice(2), forecast3Day);
            } else {
                todayLow = daily[0].temperature;
                parseForecast(daily.slice(1), forecast3Day);
            }
        }

        const city = pointsData.properties.relativeLocation.properties.city;
        const stateCode = pointsData.properties.relativeLocation.properties.state;

        return {
            location: `${city}, ${stateCode}`,
            temp: current.temperature,
            unit: current.temperatureUnit,
            condition: current.shortForecast,
            icon: getEmoji(current.shortForecast),
            high: todayHigh,
            low: todayLow,
            forecast3Day
        };
    } catch (e) {
        console.error("Weather fetch error:", e);
        return null;
    }
}

function parseForecast(periods, target) {
    let collectedCount = 0;
    for (let i = 0; i < periods.length && collectedCount < 3; i++) {
        if (periods[i].isDaytime) {
            const high = periods[i].temperature;
            const low = (i + 1 < periods.length) ? periods[i + 1].temperature : "N/A";
            target.push({
                name: periods[i].name.substring(0, 3),
                high: high,
                low: low,
                condition: periods[i].shortForecast,
                icon: getEmoji(periods[i].shortForecast)
            });
            collectedCount++;
            i++; // Skip night
        }
    }
}

// --- Persistence ---

function saveToStorage() {
    const dataToSave = state.locations.map(loc => ({ zip: loc.zip, name: loc.name }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(dataToSave));
}

async function loadFromStorage() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
        const parsed = JSON.parse(saved);
        for (const loc of parsed) {
            await addLocation(loc.zip, loc.name, false);
        }
    }
}

// --- UI Rendering ---

function renderTabs() {
    const tabBar = document.getElementById('tab-bar');
    tabBar.innerHTML = '';
    
    state.locations.forEach(loc => {
        const tab = document.createElement('div');
        tab.className = `tab ${state.activeZip === loc.zip ? 'active' : ''}`;
        
        let label = loc.name || loc.zip;
        if (label.length > 8) label = label.substring(0, 6) + '..';
        
        tab.textContent = label;
        tab.onclick = () => setActiveLocation(loc.zip);
        tabBar.appendChild(tab);
    });
}

function renderContent() {
    const container = document.getElementById('weather-card-container');
    const activeLoc = state.locations.find(l => l.zip === state.activeZip);

    if (!activeLoc) {
        document.getElementById('empty-state').style.display = 'block';
        container.innerHTML = '';
        return;
    }

    document.getElementById('empty-state').style.display = 'none';
    const data = activeLoc.weatherData;

    container.innerHTML = `
        <div class="weather-card">
            <button class="remove-btn" onclick="removeLocation('${activeLoc.zip}')">✕</button>
            
            <div class="location-name">${activeLoc.name || data.location}</div>
            <div class="location-sub">${activeLoc.name ? data.location + ' • ' : ''}${activeLoc.zip}</div>
            
            <div class="current-weather">
                <div class="current-temp">${data.temp}°</div>
                <div class="current-icon">${data.icon}</div>
            </div>
            
            <div class="current-condition">${data.condition}</div>
            
            <hr>
            
            <div class="forecast-list">
                ${data.forecast3Day.map(day => `
                    <div class="forecast-row">
                        <div class="day-name">${day.name}</div>
                        <div class="forecast-icon">${day.icon}</div>
                        <div class="temp-item high">H: ${day.high}°</div>
                        <div class="temp-item low">L: ${day.low}°</div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// --- Actions ---

async function addLocation(zip, name, shouldSave = true) {
    if (state.locations.find(l => l.zip === zip)) return;

    const coords = await getCoordinates(zip);
    if (!coords) {
        if (shouldSave) alert("Invalid Zip code.");
        return;
    }

    const weatherData = await getWeatherData(coords.lat, coords.lon);
    if (!weatherData) return;

    state.locations.push({ zip, name, weatherData });
    state.activeZip = zip;
    
    if (shouldSave) saveToStorage();
    renderTabs();
    renderContent();
}

function removeLocation(zip) {
    state.locations = state.locations.filter(l => l.zip !== zip);
    if (state.activeZip === zip) {
        state.activeZip = state.locations.length > 0 ? state.locations[0].zip : null;
    }
    saveToStorage();
    renderTabs();
    renderContent();
}

function setActiveLocation(zip) {
    state.activeZip = zip;
    renderTabs();
    renderContent();
}

// --- Initialization ---

document.getElementById('add-btn').onclick = () => {
    const name = document.getElementById('name-input').value.trim();
    const zip = document.getElementById('zip-input').value.trim();
    if (zip) {
        addLocation(zip, name);
        document.getElementById('name-input').value = '';
        document.getElementById('zip-input').value = '';
    }
};

// Handle Enter key on inputs
document.querySelectorAll('input').forEach(input => {
    input.onkeypress = (e) => {
        if (e.key === 'Enter') {
            if (input.id === 'name-input') document.getElementById('zip-input').focus();
            else document.getElementById('add-btn').click();
        }
    };
});

window.onload = loadFromStorage;
