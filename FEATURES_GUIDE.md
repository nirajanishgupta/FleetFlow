# 🚛 Routing Dashboard - Feature Guide

## New Features Added

### 1. **Multi-Vehicle Fleet Configuration** 🚚

Configure up to 5 different vehicle types:

```
Vehicle Type 1: "Bolero"
- Capacity: 120 crates
- Count: 10 vehicles

Vehicle Type 2: "Bada Dost"  
- Capacity: 108 crates
- Count: 6 vehicles

Vehicle Type 3: "Mini Truck"
- Capacity: 80 crates
- Count: 5 vehicles
```

**How it works:**
- Routes assigned to best-fit vehicle (largest capacity first)
- Respects available count for each type
- Shows fleet usage: "Used 8/10 Bolero, 3/6 Bada Dost"

### 2. **Vehicle Count Constraint** 📊

Limits total routes to available vehicles:
- If you have 10 Bolero + 6 Bada Dost = 16 total vehicles
- Maximum 16 routes will be created
- Excess stores marked as "Unassigned"

### 3. **Unloading Time** ⏱️

Separate from travel time:
- **Load Time**: Time to load vehicle at plant (e.g., 15 min)
- **Unload Time**: Time per delivery stop (e.g., 15 min)
- **Travel Time**: Calculated from distance ÷ speed

**ETA Calculation:**
```
Dispatch: 05:00
  + Travel to Stop1 (10 min)
  + Unload at Stop1 (15 min)
ETA Stop1: 05:25

  + Travel to Stop2 (8 min)
  + Unload at Stop2 (15 min)
ETA Stop2: 05:48
```

### 4. **Max Round Trip Distance** 🛣️

Constraint on total route distance:
- Set max km per route (e.g., 150 km)
- Prevents excessively long routes
- Routes exceeding limit won't merge

**Example:**
- Max RT Distance: 150 km
- Route A (80 km) can merge with nearby stores
- Route B (140 km) cannot add more stops

### 5. **Round Trip Path: 123321** 🔄

Routes return through same stops in reverse:

```
Traditional:     Plant → 1 → 2 → 3 → Plant (direct return)
New (123321):    Plant → 1 → 2 → 3 → 2 → 1 → Plant

Distance = Forward path + Return through same stops
```

**Why?**
- More realistic for delivery scenarios
- Accounts for one-way streets, traffic patterns
- Driver retraces familiar path

## UI Updates

### Sidebar Configuration

```
📍 Plant Location
   - Lat/Lon
   - Name

🚛 Fleet Configuration
   ├─ Number of Vehicle Types (1-5)
   ├─ Vehicle Type 1
   │  ├─ Name
   │  ├─ Capacity
   │  └─ Count
   └─ Vehicle Type 2...

⚙️ Routing Constraints
   ├─ Max Utilization %
   ├─ Max Stops per Route
   └─ Max Round Trip Distance (km)

🕐 Operations
   ├─ Loading Start Time
   ├─ Number of Docks
   ├─ Load Time (min)
   ├─ Unload Time (min)
   ├─ Avg Speed (km/h)
   └─ ☐ Use Real Road Distance
```

### Results Display

**KPIs:**
- Routes | Stores | Crates | Total km (RT) | Unassigned

**Fleet Usage:**
```
Bolero        Bada Dost     Mini Truck
8/10          3/6           0/5
120 crates    108 crates    80 crates
```

**Route Table Columns:**
- Route | Vehicle | Seq | Store_ID | Store_Name | Crates | ETA | Dispatch | Route_Crates | Vehicle_Cap | Util% | RT_Distance_km

## Example Scenario

**Input:**
- 50 stores, total 2,500 crates
- Fleet: 10 Bolero (120 cr), 5 Bada Dost (108 cr)
- Max util: 90%
- Max stops: 6
- Max distance: 150 km
- Unload time: 15 min/stop

**Output:**
- 12 routes created (uses 12/15 available vehicles)
- 8 routes use Bolero (capacity needed)
- 4 routes use Bada Dost (smaller loads)
- 3 vehicles unused (idle)
- 2 stores unassigned (couldn't fit within constraints)

## Tips for Configuration

**High Utilization (tight fleet):**
- Increase max util to 95%
- Increase max stops to 8
- Increase max distance to 200 km

**Conservative (reliability):**
- Keep max util at 85%
- Limit stops to 4-5
- Set max distance to 100 km

**Mixed Fleet Strategy:**
- Large vehicles for dense urban areas (many small stops)
- Small vehicles for sparse rural areas (few large stops)
- Medium vehicles for flexibility

## Technical Notes

**Vehicle Assignment Logic:**
1. Sort vehicles by capacity (largest first)
2. For each route, find smallest vehicle that fits
3. Remove assigned vehicle from available pool
4. If no vehicle fits, mark stores as unassigned

**Distance Calculation:**
- Haversine (straight-line): Fast, approximate
- OSRM API (real roads): Accurate, requires internet
- Round trip: 2× forward path (symmetric)

**Complexity:**
- Algorithm: O(n²) for savings calculation
- Vehicle assignment: O(routes × vehicle_types)
- Suitable for up to 500 stores
