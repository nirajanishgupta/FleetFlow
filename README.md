# 🚛 Vehicle Routing Dashboard

**Clarke-Wright Algorithm | Multi-Vehicle Fleet | 85-90% Utilization**

---

## 📦 Package Contents

```
routing-dashboard-package/
├── routing_dashboard.py          # Main application ✅
├── requirements.txt              # Python dependencies
├── SETUP_INSTRUCTIONS.md         # Quick start guide
├── FEATURES_GUIDE.md             # Feature documentation
├── sample_data.csv              # Example dataset
└── README.md                     # This file
```

---

## ⚡ Quick Start (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Dashboard
```bash
python3 -m streamlit run main.py
```

Opens at: **http://localhost:8501**

### 3. Upload CSV & Configure → Run Simulation → Download Results

---

## 📊 What This Does

**Input:** CSV with store locations + demands  
**Output:** Optimized delivery routes for your fleet

**Key Features:**
- ✅ 85-90% vehicle utilization (never exceed capacity)
- ✅ Multi-vehicle fleet (up to 5 types)
- ✅ Clustering for efficient routes
- ✅ Interactive HTML map with toggle controls
- ✅ Excel/CSV export
- ✅ Collapsible unassigned stores UI

---

## 📋 Requirements

**System:**
- Python 3.8+
- 4GB RAM
- Internet (one-time setup)

**Data:**
- CSV with: Store_ID, Store_Name, Latitude, Longitude, Demand_Crates
- Plant location coordinates
- Fleet configuration (vehicle types, capacities, counts)

---

## 🎯 How Routing Works

### Step-by-Step Logic

**1. Data Processing**
- Upload CSV with store locations and demand
- Validate coordinates and demand values
- Calculate distance matrix (haversine formula for geo-distances)
- Identify plant/warehouse location as route origin

**2. Route Optimization**
- Apply **Clarke-Wright Savings Algorithm** to minimize total distance
- Group stores into clusters based on proximity
- Balance vehicle loads to maximize fleet utilization
- Respect operational constraints (capacity, distance, stops)

**3. Vehicle Assignment**
- Match routes to available fleet based on demand
- Prioritize best-fit allocation (minimize excess capacity)
- Handle multi-vehicle types (Large/Medium/Small)
- Track unassigned stores for review

**4. Visualization & Export**
- Generate interactive map with color-coded routes
- Export detailed route sheets (CSV/Excel)
- Provide utilization metrics and insights

---

## 🧮 Algorithm Details

### Clarke-Wright Savings Heuristic

**Core Formula:**
```
Savings(i,j) = Distance(Plant→i) + Distance(Plant→j) - Distance(i→j)
```

**Why it works:** Combining two stops (i,j) into one route saves the duplicate plant trips.

**Optimization Steps:**

1. **Initialize** - Each store starts as a separate route
2. **Calculate Savings** - Compute savings for all store pairs
3. **Sort Savings** - Highest savings first (greedy approach)
4. **Merge Routes** - Iteratively combine routes if:
   - Total demand ≤ vehicle capacity × max utilization%
   - Total stops ≤ max stops constraint
   - Round trip distance ≤ max distance limit
   - Vehicles available in fleet
5. **Pack Aggressively** - Target 85-90% utilization to minimize fleet size
6. **Assign Vehicles** - Best-fit allocation based on route demand

**Constraints Applied:**
- ✅ Max utilization: 85-90% (prevent overload while maximizing efficiency)
- ✅ Max stops per route: 5-6 (driver workload, time window)
- ✅ Max round trip distance: 150 km (driver shift, fuel efficiency)
- ✅ Vehicle availability: Respect fleet count limits

**Distance Calculation:**
```python
# Haversine formula for geographic distance
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat/2)² + cos(lat1) × cos(lat2) × sin(dLon/2)²
    c = 2 × atan2(√a, √(1-a))
    return R × c
```

---

## 🌍 Use Cases

### 1. **Disaster Management & Business Continuity**

**Scenario: Warehouse Flood/Damage**
- ⚠️ **Problem:** Warehouse A flooded, cannot service 50 stores
- ✅ **Solution:** One-click route redistribution
  1. Upload store list with new plant coordinates (Warehouse B)
  2. Run simulation with existing fleet config
  3. Download new routes in seconds
  4. Dispatch teams with updated maps

**Benefits:**
- Zero manual planning time
- Immediate alternative routing
- Maintain customer service during crisis
- Clear visibility of coverage gaps

---

### 2. **Seasonal Demand Fluctuation**

**Scenario: Festival/Holiday Peak**
- 📈 **Problem:** Demand doubles, existing routes overloaded
- ✅ **Solution:** Dynamic fleet scaling
  - Adjust vehicle counts in sidebar
  - Re-run optimization with higher utilization targets
  - Identify additional vehicles needed
  - Export updated routes for expanded fleet

---

### 3. **New Store Onboarding**

**Scenario: 10 New Stores Launch**
- 🆕 **Problem:** Integrate new locations into delivery network
- ✅ **Solution:** Add rows to CSV → Re-upload → Optimize
  - Algorithm automatically clusters new stores
  - Merges into existing routes where capacity allows
  - Creates new routes if demand exceeds current fleet
  - Zero disruption to existing operations

---

### 4. **Cost Optimization & Fleet Rightsizing**

**Scenario: Reduce Logistics Costs**
- 💰 **Problem:** Underutilized vehicles, high fuel costs
- ✅ **Solution:** Experiment with constraints
  - Increase max stops (6→8) to consolidate routes
  - Increase utilization target (85%→90%)
  - Compare scenarios to find optimal fleet mix
  - Reduce vehicles by 10-15% while maintaining coverage

---

### 5. **Multi-Warehouse Network Rebalancing**

**Scenario: Open New Regional Warehouse**
- 🏭 **Problem:** Split 200-store network between 2 warehouses
- ✅ **Solution:** Run parallel simulations
  - **Simulation A:** Stores 1-120 from Warehouse A
  - **Simulation B:** Stores 121-200 from Warehouse B
  - Compare total distance, vehicle count, utilization
  - Choose optimal split based on metrics

**One-Click Workflow:**
1. Filter CSV by region → Upload to dashboard
2. Enter warehouse coordinates
3. Run optimization (15 seconds)
4. Download routes → Share with dispatch teams
5. Repeat for other regions

---

### 6. **Emergency Rerouting**

**Scenario: Road Closure/Strike**
- 🚧 **Problem:** Highway blocked, 30 stores unreachable via usual routes
- ✅ **Solution:** Exclude affected stores → Re-optimize
  - Remove stores from CSV temporarily
  - Run optimization for reachable stores
  - Create manual backup plan for excluded stores
  - Restore normal routes when access returns

---

### 7. **Daily Operations & What-If Planning**

**Day-to-Day Benefits:**
- ⚡ **Same-Day Route Adjustments:** Store closure? Update CSV, rerun in 1 minute
- 📊 **Capacity Planning:** Test "what if we add 3 more vehicles?"
- 🎯 **Territory Design:** Optimize zones before assigning permanent drivers
- 📦 **Demand Forecasting:** Model future demand scenarios
- 🚚 **Fleet Procurement:** Justify vehicle purchases with utilization data

---

### Key Advantage: **One-Click Simplicity**

Traditional routing tools require:
- ❌ Hours of manual planning
- ❌ Complex software training
- ❌ Expensive enterprise licenses
- ❌ IT support for changes

**This Dashboard:**
- ✅ Upload CSV → Configure → Click "Run" → Download
- ✅ No coding/training required
- ✅ Instant what-if scenarios
- ✅ Works offline after setup
- ✅ Share results as self-contained HTML maps

---

## 📖 Documentation

- **SETUP_INSTRUCTIONS.md** - Installation & usage
- **FEATURES_GUIDE.md** - Detailed feature list
- **sample_data.csv** - Example CSV format

---

## 🔧 Troubleshooting

**Module not found:**
```bash
pip install --upgrade streamlit pandas openpyxl
```

**Port in use:**
```bash
streamlit run routing_dashboard.py --server.port 8502
```

**No routes created:**
- Check total demand fits in fleet capacity
- Reduce utilization constraint (try 85%)
- Increase max stops (try 7-8)

---

## 💡 Tips

**Upload your own CSV:**
1. Must have: Store_ID, Name, Lat, Lon, Demand columns
2. Auto-detects column name variations
3. Handles float crates (rounds automatically)
4. Auto-scales if total < 200 crates

**Configure fleet:**
- Large vehicles (120 crates) for urban high-demand routes
- Medium vehicles (90 crates) for suburban areas
- Small vehicles (60 crates) for sparse regions

**Tune constraints:**
- Higher util% = fewer vehicles needed
- More stops = better coverage, longer routes
- Lower distance = tighter clustering

---

## 📤 Sharing Results

**HTML Map:**
- Self-contained file
- Works offline (needs internet for map tiles)
- Share via email, USB, cloud

**CSV/Excel:**
- Full route details
- Import to ERP/WMS systems
- Print for dispatch team

---

## ✨ Latest Updates

- [x] Collapsible unassigned stores (× button)
- [x] Toggle unassigned map markers
- [x] No page refresh on downloads
- [x] Multi-vehicle optimization
- [x] Excel export with formatting

---

**Built with:** Python, Streamlit, Leaflet.js  
**Algorithm:** Clarke-Wright Savings Heuristic  
**Ready in 5 minutes** ⚡
