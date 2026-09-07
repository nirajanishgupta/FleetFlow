# 🚛 Routing Dashboard - Setup Guide

## Prerequisites
- Python 3.8+ installed ([Download](https://www.python.org/downloads/))
- Internet (one-time setup only)

## Installation (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Dashboard
```bash
streamlit run routing_dashboard.py
```

Dashboard opens at: **http://localhost:8501**

---

## Quick Start

### Step 1: Upload CSV

Your CSV must have these columns:
- `Store_ID` or `Buyer_Outlet_ID`
- `Store_Name` or `Buyer_Outlet_Name`
- `Latitude` or `lat`
- `Longitude` or `lon`
- `Demand_Crates` or `Demand`

### Step 2: Configure Fleet

**Plant Location:**
- Latitude, Longitude, Name

**Vehicle Types:**
- Add 1-5 vehicle types
- Each with: Name, Capacity (crates), Count available

**Routing Constraints:**
- Max Utilization: 85-90% (don't exceed capacity)
- Max Stops: 5-6 per route
- Max Distance: 150 km round trip

**Operations:**
- Start time: 05:00 AM
- Docks: 4
- Load time: 30 min
- Unload time: 15 min per stop
- Speed: 30 km/h

### Step 3: Run Simulation

Click **"Run Simulation"** → Wait 5-10 seconds

### Step 4: View Results

**Interactive Map:**
- Click route → view only that route
- Shift+Click → toggle multiple routes
- Toggle Unassigned → show/hide unassigned stores
- × button → collapse unassigned list

**Download Files:**
- 📄 HTML Map (interactive, shareable)
- 📊 CSV Table (route details)
- 📈 Excel File (formatted report)

---

## Troubleshooting

**"Port already in use":**
```bash
streamlit run routing_dashboard.py --server.port 8502
```

**"Module not found":**
```bash
pip install --upgrade streamlit pandas openpyxl
```

**CSV upload fails:**
- Check column names match the accepted formats
- Remove empty rows
- Ensure UTF-8 encoding
- Check decimal format (use `.` not `,`)

**No routes created:**
- Check total demand vs vehicle capacity
- Reduce max utilization constraint
- Increase max stops allowed
- Increase max distance

---

## Features

✅ **Clarke-Wright Algorithm** - Optimized routing  
✅ **Multi-Vehicle Fleet** - Up to 5 vehicle types  
✅ **85-90% Utilization** - Aggressive packing  
✅ **Interactive Map** - Toggle routes, zoom stores  
✅ **Collapsible UI** - Hide unassigned stores  
✅ **No Refresh Downloads** - Results persist  
✅ **Excel Export** - Formatted reports  

---

## CSV Format Example

```csv
Store_ID,Store_Name,Latitude,Longitude,Demand_Crates
S001,Store Delhi North,28.7041,77.1025,45
S002,Store Delhi East,28.6139,77.2090,38
S003,Store Gurgaon,28.4595,77.0266,52
```

**Auto-formats:**
- Float crates (4.39 → 4)
- Different column names
- Unit scaling (if total < 200 crates)

---

## Tips

**High Coverage (assign more stores):**
- Max util: 90%
- Max stops: 7-8
- Max distance: 200 km

**Conservative (reliability):**
- Max util: 85%
- Max stops: 4-5
- Max distance: 100 km

**Balanced (recommended):**
- Max util: 88%
- Max stops: 6
- Max distance: 150 km

---

## Support

For issues or questions, refer to:
- `FEATURES_GUIDE.md` - Feature documentation
- `SHARING_GUIDE.md` - Sharing instructions

---

**Ready in 5 minutes** ⚡
