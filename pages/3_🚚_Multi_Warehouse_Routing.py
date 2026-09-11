#!/usr/bin/env python3
"""Clarke-Wright Vehicle Routing Dashboard - Refactored"""
import streamlit as st
import pandas as pd
import json
import math
import requests
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

# Constants
TARGET_UTIL_BUFFER = 0.05
MIN_UTIL_BUFFER = 0.15
ROUTE_COLORS = [
    '#e53939', '#e56139', '#e58839', '#e5b039', '#e5d839', '#cbe539',
    '#a3e539', '#7be539', '#53e539', '#39e546', '#39e56e', '#39e596'
]
OSRM_TIMEOUT = 5
EARTH_RADIUS_KM = 6371

st.set_page_config(page_title="Vehicle Routing Simulator", layout="wide")

if 'results' not in st.session_state:
    st.session_state.results = None


# === Distance Calculations ===

def haversine(p1, p2):
    """Calculate great-circle distance between two (lat, lon) points in km."""
    lat1, lon1 = p1
    lat2, lon2 = p2
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def route_distance(points):
    """Calculate total distance through a sequence of (lat, lon) points."""
    return sum(haversine(points[i], points[i+1]) for i in range(len(points)-1))


def get_osrm_distance(points):
    """Get real road distance via OSRM API, fallback to Haversine on failure.
    Returns (distance_km, used_osrm_bool)"""
    try:
        # OSRM expects lon,lat order
        coords_str = ';'.join([f"{lon},{lat}" for lat, lon in points])
        url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=false"
        resp = requests.get(url, timeout=OSRM_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()['routes'][0]['distance'] / 1000, True  # meters to km
    except Exception as e:
        print(f"⚠️ OSRM API failed ({e}), using Haversine fallback")

    return route_distance(points), False


def calculate_route_distance(points, use_osrm):
    """Calculate round-trip distance for a route (includes return to depot).
    Returns (distance_km, method_used_string)"""
    loop = points + [points[0]]  # Complete the loop back to depot
    if use_osrm:
        dist, success = get_osrm_distance(loop)
        method = "OSRM" if success else "Haversine (OSRM fallback)"
        return dist, method
    return route_distance(loop), "Haversine"


# === Route Packing Helper ===

def pack_route_to_target(initial_route, vehicle, remaining_stores, stores, plant,
                         target_util, max_util, max_stops, max_km):
    """
    Pack additional stores into a route to reach target utilization.
    Returns (final_route, final_crates) or None if constraints violated.
    """
    route = list(initial_route)
    crates = sum(stores[i]['crates'] for i in route)
    target_crates = vehicle['cap'] * target_util
    max_crates = vehicle['cap'] * max_util

    while crates < target_crates and remaining_stores and len(route) < max_stops:
        # Find nearest unassigned store
        last_store = stores[route[-1]]
        nearest = min(remaining_stores,
                     key=lambda s: haversine((last_store['lat'], last_store['lon']),
                                            (stores[s]['lat'], stores[s]['lon'])))

        new_crates = crates + stores[nearest]['crates']
        if new_crates > max_crates:
            break

        # Check distance constraint
        test_route = route + [nearest]
        points = [(plant['lat'], plant['lon'])] + [(stores[i]['lat'], stores[i]['lon']) for i in test_route]
        if route_distance(points + [points[0]]) > max_km:
            break

        route.append(nearest)
        crates = new_crates
        remaining_stores.remove(nearest)

    return route, crates


# === Clarke-Wright Algorithm ===

def clarke_wright(stores, plant, vehicles, max_stops, max_util, min_util, max_km, base_time,
                  docks, load_time, unload_time, speed, use_osrm, delivery_model):

    # === Input Validation ===
    if not stores or len(stores) == 0:
        raise ValueError("No stores to route. Please upload a valid CSV with store data.")

    # Validate vehicles
    if not vehicles or len(vehicles) == 0:
        raise ValueError("No vehicles configured. Please add at least one vehicle type.")

    for vtype, vdata in vehicles.items():
        if vdata['capacity'] <= 0:
            raise ValueError(f"Vehicle '{vtype}' has invalid capacity: {vdata['capacity']}. Must be > 0.")
        if vdata['cost'] < 0:
            raise ValueError(f"Vehicle '{vtype}' has invalid cost: {vdata['cost']}. Must be >= 0.")
        if vdata['count'] <= 0:
            raise ValueError(f"Vehicle '{vtype}' has invalid count: {vdata['count']}. Must be > 0.")

    # Validate stores have positive demand
    invalid_stores = [s for s in stores if s.get('crates', 0) <= 0]
    if invalid_stores:
        raise ValueError(f"{len(invalid_stores)} stores have invalid demand (<= 0 crates). Please check your data.")

    # Calculate savings for all store pairs
    savings = []
    for i, s1 in enumerate(stores):
        for j, s2 in enumerate(stores[i+1:], i+1):
            p = (plant['lat'], plant['lon'])
            p1 = (s1['lat'], s1['lon'])
            p2 = (s2['lat'], s2['lon'])
            sav = haversine(p, p1) + haversine(p, p2) - haversine(p1, p2)
            savings.append((sav, i, j))
    savings.sort(reverse=True)

    # Build vehicle type list with cost info
    veh_list = []
    for vtype, vdata in vehicles.items():
        veh_list.append({
            'type': vtype,
            'cap': vdata['capacity'],
            'cost': vdata['cost'],
            'count_available': vdata['count']
        })

    min_veh_cap = min(v['cap'] for v in veh_list) if veh_list else 120

    # Initialize routes (one store per route)
    routes = [[i] for i in range(len(stores))]

    # Merge routes based on savings
    for sav, i, j in savings:
        ri = next((r for r in routes if i in r), None)
        rj = next((r for r in routes if j in r), None)

        if ri is None or rj is None or ri == rj:
            continue

        total_crates = sum(stores[k]['crates'] for k in ri) + sum(stores[k]['crates'] for k in rj)
        total_stops = len(ri) + len(rj)

        if total_crates > min_veh_cap * max_util or total_stops > max_stops:
            continue

        # Check if routes can be joined end-to-end
        can_join_ji = ri[0] == i and rj[-1] == j
        can_join_ij = ri[-1] == i and rj[0] == j

        if not (can_join_ji or can_join_ij):
            continue

        merged = (rj + ri) if can_join_ji else (ri + rj)

        # Check distance constraint
        points = [(plant['lat'], plant['lon'])] + [(stores[k]['lat'], stores[k]['lon']) for k in merged]
        if route_distance(points + [points[0]]) > max_km:
            continue

        routes.remove(ri)
        routes.remove(rj)
        routes.append(merged)

    # ponytail: filter routes that violate max_km (catches single-store routes too far from plant)
    valid_routes = []
    for route in routes:
        points = [(plant['lat'], plant['lon'])] + [(stores[k]['lat'], stores[k]['lon']) for k in route]
        if route_distance(points + [points[0]]) <= max_km:
            valid_routes.append(route)
    routes = valid_routes

    # === Cost-Minimized Vehicle Assignment ===
    target_util = max_util - TARGET_UTIL_BUFFER
    # min_util now passed as parameter from user input

    # Sort routes by load (largest first) - assign big routes first
    route_loads = [(r, sum(stores[k]['crates'] for k in r)) for r in routes]
    route_loads.sort(key=lambda x: x[1], reverse=True)

    # Track available vehicle count by type
    vehicle_availability = {v['type']: v['count_available'] for v in veh_list}

    packed_routes = []
    all_stores = set(range(len(stores)))
    assigned_stores = set()

    # Pack existing Clarke-Wright routes with cost minimization
    for route, crates in route_loads:
        if any(s in assigned_stores for s in route):
            continue

        # Find cheapest available vehicle that fits (after packing)
        remaining = list(all_stores - assigned_stores - set(route))
        best_vehicle = None
        best_cost_per_crate = float('inf')
        best_packed_route = None
        best_packed_crates = 0

        for vehicle in veh_list:
            # Check if this vehicle type is available
            if vehicle_availability[vehicle['type']] == 0:
                continue

            # Check if base route fits
            if crates > vehicle['cap'] * max_util:
                continue

            # Try packing to target utilization
            test_remaining = list(remaining)
            final_route, final_crates = pack_route_to_target(
                route, vehicle, test_remaining, stores, plant,
                target_util, max_util, max_stops, max_km
            )

            # ponytail: final validation - ensure doesn't exceed max_util
            if final_crates > vehicle['cap'] * max_util:
                continue

            # Check if meets minimum utilization
            if final_crates < vehicle['cap'] * min_util:
                continue

            # Calculate cost per crate for this assignment
            if final_crates == 0:
                continue  # Skip if no crates (shouldn't happen but safety check)
            cost_per_crate = vehicle['cost'] / final_crates

            # Is this the cheapest option so far?
            if cost_per_crate < best_cost_per_crate:
                best_cost_per_crate = cost_per_crate
                best_vehicle = vehicle
                best_packed_route = final_route
                best_packed_crates = final_crates

        # Assign to cheapest available vehicle
        if best_vehicle:
            vehicle_availability[best_vehicle['type']] -= 1
            assigned_stores.update(best_packed_route)
            packed_routes.append((best_packed_route, best_vehicle))

    # Create new routes for remaining stores with cost minimization
    remaining = list(all_stores - assigned_stores)

    while remaining:
        # Find cheapest available vehicle
        available_veh = [v for v in veh_list if vehicle_availability[v['type']] > 0]
        if not available_veh:
            break  # No vehicles left

        best_vehicle = None
        best_cost_per_crate = float('inf')
        best_route = None
        best_crates = 0

        for vehicle in available_veh:
            # Start with nearest store to plant
            start_store = min(remaining,
                             key=lambda s: haversine((plant['lat'], plant['lon']),
                                                    (stores[s]['lat'], stores[s]['lon'])))
            test_route = [start_store]

            # ponytail: skip if single store already > max_km
            points = [(plant['lat'], plant['lon']), (stores[start_store]['lat'], stores[start_store]['lon'])]
            if route_distance(points + [points[0]]) > max_km:
                continue

            test_remaining = [s for s in remaining if s != start_store]

            # Pack to target
            final_route, final_crates = pack_route_to_target(
                test_route, vehicle, test_remaining, stores, plant,
                target_util, max_util, max_stops, max_km
            )

            # ponytail: final validation - ensure doesn't exceed max_util
            if final_crates > vehicle['cap'] * max_util:
                continue

            # Check if meets minimum utilization
            if final_crates < vehicle['cap'] * min_util:
                continue

            # Calculate cost per crate
            if final_crates == 0:
                continue  # Skip if no crates (shouldn't happen but safety check)
            cost_per_crate = vehicle['cost'] / final_crates

            if cost_per_crate < best_cost_per_crate:
                best_cost_per_crate = cost_per_crate
                best_vehicle = vehicle
                best_route = final_route
                best_crates = final_crates

        if best_vehicle:
            vehicle_availability[best_vehicle['type']] -= 1
            assigned_stores.update(best_route)
            packed_routes.append((best_route, best_vehicle))
            remaining = [s for s in remaining if s not in best_route]
        else:
            # No suitable vehicle found for remaining stores
            print(f"⚠️ Warning: {len(remaining)} stores cannot be assigned - all vehicles exhausted or constraints too tight")
            break

    # === Generate Route Details ===
    unassigned = [stores[i] for i in (all_stores - assigned_stores)]
    base_dt = datetime.strptime(base_time, "%H:%M")
    route_data = []
    distance_methods = set()  # Track which methods were actually used

    for rn, (route, vehicle) in enumerate(packed_routes, 1):
        crates = sum(stores[k]['crates'] for k in route)

        # Build route based on delivery model
        if delivery_model == 'forward_reverse':
            # 123321: Forward for delivery, reverse for pickup
            # Route: plant → 1 → 2 → 3 → 2 → 1 → plant
            forward_stores = route
            reverse_stores = list(reversed(route[:-1]))  # Skip last store (already there)
            all_route_stops = forward_stores + reverse_stores
            points = [(plant['lat'], plant['lon'])] + \
                     [(stores[k]['lat'], stores[k]['lon']) for k in forward_stores] + \
                     [(stores[k]['lat'], stores[k]['lon']) for k in reverse_stores]
        else:
            # 112233: Standard - deliver + pickup at each stop
            all_route_stops = route
            points = [(plant['lat'], plant['lon'])] + [(stores[k]['lat'], stores[k]['lon']) for k in route]

        total_dist, dist_method = calculate_route_distance(points, use_osrm)
        distance_methods.add(dist_method)

        wave = (rn - 1) // docks
        dispatch = base_dt + timedelta(minutes=load_time * wave)

        # Calculate ETAs based on delivery model
        stops = []
        current_time = dispatch

        if delivery_model == 'forward_reverse':
            # Create mapping of store index to sequence number
            store_to_seq = {idx: seq for seq, idx in enumerate(route, 1)}

            # Forward pass: deliveries only
            for seq, idx in enumerate(route, 1):
                store = stores[idx]
                prev_point = points[seq - 1]
                curr_point = (store['lat'], store['lon'])
                travel_time = haversine(prev_point, curr_point) / speed * 60
                current_time += timedelta(minutes=travel_time + unload_time)

                stops.append({
                    'seq': seq,
                    'id': store['id'],
                    'name': store['name'] + ' (Deliver)',
                    'lat': store['lat'],
                    'lon': store['lon'],
                    'crates': store['crates'],
                    'eta': current_time.strftime("%I:%M %p")
                })

            # Reverse pass: pickups only (skip last store, already there)
            for i, idx in enumerate(reversed(route[:-1]), 1):
                store = stores[idx]
                prev_point = points[len(route) + i - 1]
                curr_point = (store['lat'], store['lon'])
                travel_time = haversine(prev_point, curr_point) / speed * 60
                current_time += timedelta(minutes=travel_time + unload_time)

                stops.append({
                    'seq': store_to_seq[idx],  # Use original sequence number
                    'id': store['id'],
                    'name': store['name'] + ' (Pickup)',
                    'lat': store['lat'],
                    'lon': store['lon'],
                    'crates': store['crates'],  # Empty crates being picked up (same count as delivered)
                    'eta': current_time.strftime("%I:%M %p")
                })
        else:
            # Standard: deliver + pickup at each stop
            for seq, idx in enumerate(route, 1):
                store = stores[idx]
                prev_point = points[seq - 1]
                curr_point = (store['lat'], store['lon'])
                travel_time = haversine(prev_point, curr_point) / speed * 60
                current_time += timedelta(minutes=travel_time + unload_time)

                stops.append({
                    'seq': seq,
                    'id': store['id'],
                    'name': store['name'],
                    'lat': store['lat'],
                    'lon': store['lon'],
                    'crates': store['crates'],
                    'eta': current_time.strftime("%I:%M %p")
                })

        route_data.append({
            'rn': rn,
            'veh': vehicle['type'],
            'crates': crates,
            'cap': vehicle['cap'],
            'util': round(crates / vehicle['cap'] * 100, 1) if vehicle['cap'] > 0 else 0,
            'dist': round(total_dist, 1),
            'dispatch': dispatch.strftime("%I:%M %p"),
            'drops': len(stops),  # Number of actual stops (includes both delivery & pickup for 123321)
            'stops': stops,
            'cost': vehicle['cost'],
            'cost_per_crate': round(vehicle['cost'] / crates, 2) if crates > 0 else 0
        })

    # Sort by distance (longest first) and assign colors
    route_data.sort(key=lambda x: x['dist'], reverse=True)
    for i, r in enumerate(route_data, 1):
        r['rn'] = i
        r['color'] = ROUTE_COLORS[(i - 1) % len(ROUTE_COLORS)]

    return route_data, unassigned, distance_methods


# === HTML Map Generation ===

def generate_html(data):
    """Generate standalone HTML with Leaflet map."""
    max_util_pct = data.get('max_util', 90)
    plant = data['plant']
    distance_method = data.get('distance_method', 'Unknown')
    delivery_model = data.get('delivery_model', 'Standard')

    # Read template if exists, otherwise use inline
    template_path = Path(__file__).parent / 'map_template.html'

    if template_path.exists():
        html = template_path.read_text()
        # Simple template substitution
        html = html.replace('{{DATA}}', json.dumps(data))
        html = html.replace('{{MAX_UTIL}}', str(max_util_pct))
        html = html.replace('{{PLANT_LAT}}', str(plant['lat']))
        html = html.replace('{{PLANT_LON}}', str(plant['lon']))
        html = html.replace('{{PLANT_NAME}}', plant['name'].upper())
        return html

    # Fallback: inline HTML (ponytail: extract to template file when edited frequently)
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width,initial-scale=1"/>
    <title>Vehicle Routing Results</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <style>
        :root {{--ink:#1F3864; --bg:#f4f6f9; --line:#d9e0ec;}}
        * {{box-sizing:border-box}}
        html,body {{margin:0; height:100%; font-family:-apple-system,Segoe UI,Arial,sans-serif}}
        #app {{display:flex; height:100vh; overflow:hidden}}
        #side {{width:360px; flex:0 0 360px; background:#fff; border-right:1px solid var(--line); display:flex; flex-direction:column}}
        #map {{flex:1}}
        header {{padding:14px 16px; background:var(--ink); color:#fff}}
        header h1 {{margin:0; font-size:15px; font-weight:700}}
        header p {{margin:4px 0 0; font-size:11px; opacity:.85}}
        .summary {{display:flex; flex-wrap:wrap; gap:6px; padding:10px 12px; border-bottom:1px solid var(--line); background:var(--bg)}}
        .kpi {{flex:1 1 45%; background:#fff; border:1px solid var(--line); border-radius:8px; padding:7px 9px}}
        .kpi b {{display:block; font-size:15px; color:var(--ink)}}
        .kpi span {{font-size:10px; color:#667}}
        .controls {{padding:8px 12px; border-bottom:1px solid var(--line); display:flex; gap:6px; flex-wrap:wrap}}
        .controls button {{font-size:11px; padding:5px 9px; border:1px solid var(--line); background:#fff; border-radius:6px; cursor:pointer}}
        .controls button:hover {{background:var(--bg)}}
        #list {{overflow:auto; flex:1}}
        .row {{display:flex; align-items:center; gap:8px; padding:7px 12px; border-bottom:1px solid #eef1f6; cursor:pointer; font-size:12px; transition:all 0.2s}}
        .row:hover {{background:var(--bg)}}
        .row.off {{opacity:.3}}
        .sw {{width:12px; height:12px; border-radius:3px; flex:0 0 12px}}
        .row .meta {{flex:1}}
        .row .meta b {{font-size:12px}}
        .row .meta small {{display:block; color:#667; font-size:10px}}
        .badge {{font-size:9px; padding:2px 5px; border-radius:10px; background:#eef1f6; color:#445; white-space:nowrap}}
        .warn {{background:#FEE; color:#C00}}
        .unassigned-section {{padding:10px 12px; background:#FFF8E1; border-top:2px solid #FFA000}}
        .unassigned-section h3 {{margin:0 0 8px; font-size:12px; color:#F57C00; display:flex; align-items:center; justify-content:space-between}}
        .unassigned-section h3 .close-btn {{cursor:pointer; font-size:18px; font-weight:700; line-height:1; opacity:.6; transition:opacity 0.2s}}
        .unassigned-section h3 .close-btn:hover {{opacity:1}}
        .unassigned-list {{max-height:300px; overflow-y:auto; transition:all 0.3s}}
        .unassigned-list.collapsed {{max-height:0; overflow:hidden}}
        .unassigned-item {{font-size:11px; padding:4px 8px; background:#fff; margin:4px 0; border-radius:4px; border:1px solid #FFE0B2; cursor:pointer; transition:all 0.2s}}
        .unassigned-item:hover {{background:#FFE0B2; border-color:#F57C00; transform:translateX(4px)}}
        .note {{font-size:10px; color:#778; padding:8px 12px; border-top:1px solid var(--line)}}
        .leaflet-popup-content {{font-size:12px; margin:8px 10px}}
    </style>
</head>
<body>
    <div id="app">
        <div id="side">
            <header>
                <h1>{plant['name'].upper()} Routes</h1>
                <p id="sub">Clarke-Wright · {delivery_model}</p>
            </header>
            <div class="summary" id="kpis"></div>
            <div class="controls">
                <button id="all">Show all</button>
                <button id="none">Hide all</button>
                <button id="toggleUnassigned">Toggle Unassigned</button>
            </div>
            <div id="list"></div>'''

    if data.get('unassigned'):
        html += f'''
            <div class="unassigned-section">
                <h3>
                    <span>⚠ Unassigned ({len(data['unassigned'])})</span>
                    <span class="close-btn" id="closeUnassigned">×</span>
                </h3>
                <div class="unassigned-list" id="unassignedList">'''
        for u in data['unassigned']:
            html += f'''
                    <div class="unassigned-item" data-lat="{u['lat']}" data-lon="{u['lon']}">
                        <b>{u['name']}</b> · {u['crates']} crates
                    </div>'''
        html += '''
                </div>
            </div>'''

    html += f'''
            <div class="note">Click route to view · Shift+Click to toggle · Click store to zoom</div>
        </div>
        <div id="map"></div>
    </div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const DATA = {json.dumps(data)};
        const MAX_UTIL = {max_util_pct};

        const map = L.map('map').setView([{plant['lat']}, {plant['lon']}], 10);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'OSM',
            maxZoom: 18
        }}).addTo(map);

        const plantIcon = L.divIcon({{
            className: '',
            html: '<div style="background:#e8132b;border:2px solid #fff;border-radius:3px;width:16px;height:16px;box-shadow:0 0 0 2px #e8132b"></div>',
            iconSize: [16, 16]
        }});
        L.marker([DATA.plant.lat, DATA.plant.lon], {{icon: plantIcon}})
            .bindPopup('<b>' + DATA.plant.name.toUpperCase() + '</b><br>Distribution Plant')
            .addTo(map);

        const K = DATA.kpis;
        const distMethod = DATA.distance_method || 'Unknown';
        const deliveryModel = DATA.delivery_model || 'Standard';
        document.getElementById('sub').textContent = deliveryModel + ' · ' + K.routes + ' routes · ' + K.stores + ' stores · ' + distMethod;

        const kpiEl = document.getElementById('kpis');
        const formatCost = (cost) => '₹' + cost.toLocaleString('en-IN');
        [['Routes', K.routes], ['Stores', K.stores], ['Crates', K.crates],
         ['RT km', K.dist], ['Total Cost', formatCost(K.total_cost || 0)],
         ['Cost/Crate', '₹' + (K.avg_cost_per_crate || 0)]].forEach(([l, v]) => {{
            const d = document.createElement('div');
            d.className = 'kpi';
            d.innerHTML = '<b>' + v + '</b><span>' + l + '</span>';
            kpiEl.appendChild(d);
        }});

        const layers = {{}}, shown = {{}}, list = document.getElementById('list');

        DATA.routes.forEach(r => {{
            const col = r.color;
            const pts = [[DATA.plant.lat, DATA.plant.lon],
                        ...r.stops.map(s => [s.lat, s.lon]),
                        [DATA.plant.lat, DATA.plant.lon]];

            const line = L.polyline(pts, {{color: col, weight: 3, opacity: 0.85}});

            const markers = r.stops.map((s, i) => {{
                const icon = L.divIcon({{
                    className: '',
                    html: '<div style="background:' + col + ';color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3)">' + s.seq + '</div>',
                    iconSize: [22, 22],
                    iconAnchor: [11, 11]
                }});
                return L.marker([s.lat, s.lon], {{icon}})
                    .bindPopup('<b>' + s.name + '</b><br>Route ' + r.rn + ' (' + r.veh + ') · Stop ' + s.seq +
                              '<br>ETA: ' + s.eta + '<br>Crates: ' + s.crates);
            }});

            const grp = L.layerGroup([line, ...markers]);
            layers[r.rn] = grp;
            shown[r.rn] = false;

            const row = document.createElement('div');
            row.className = 'row off';
            row.id = 'row' + r.rn;

            const warnBadge = r.util > MAX_UTIL ? '<span class="badge warn">⚠' + r.util + '%</span>' : '';
            row.innerHTML = '<div class="sw" style="background:' + col + '"></div>' +
                           '<div class="meta"><b>R' + r.rn + ' · ' + r.veh + '</b>' +
                           '<small>' + r.drops + ' stops · ' + r.crates + '/' + r.cap + ' (' + r.util + '%) · ' + r.dist + ' km RT</small></div>' +
                           warnBadge + '<span class="badge">' + r.dispatch + '</span>';

            row.addEventListener('click', e => {{
                if (e.shiftKey) {{
                    if (shown[r.rn]) {{
                        map.removeLayer(grp);
                        shown[r.rn] = false;
                        row.classList.add('off');
                    }} else {{
                        grp.addTo(map);
                        shown[r.rn] = true;
                        row.classList.remove('off');
                    }}
                }} else {{
                    Object.keys(layers).forEach(k => {{
                        map.removeLayer(layers[k]);
                        document.getElementById('row' + k).classList.add('off');
                        shown[k] = false;
                    }});
                    grp.addTo(map);
                    shown[r.rn] = true;
                    row.classList.remove('off');
                    map.fitBounds(line.getBounds().pad(0.1));
                }}
            }});

            list.appendChild(row);
        }});

        let unassignedLayer, unassignedVisible = true;
        if (DATA.unassigned) {{
            const unassignedMarkers = DATA.unassigned.map(u => {{
                const icon = L.divIcon({{
                    className: '',
                    html: '<div style="background:#F57C00;border:3px solid #fff;border-radius:50%;width:18px;height:18px;box-shadow:0 0 0 2px #F57C00"></div>',
                    iconSize: [18, 18]
                }});
                const marker = L.marker([u.lat, u.lon], {{icon}})
                    .bindPopup('<b>⚠ UNASSIGNED</b><br>' + u.name + '<br>' + u.crates + ' crates<br><small>Exceeds constraints</small>');
                marker.on('click', () => {{
                    map.setView([u.lat, u.lon], 14);
                }});
                return marker;
            }});
            unassignedLayer = L.layerGroup(unassignedMarkers).addTo(map);

            document.querySelectorAll('.unassigned-item').forEach(el => {{
                el.addEventListener('click', () => {{
                    const lat = parseFloat(el.dataset.lat), lon = parseFloat(el.dataset.lon);
                    map.setView([lat, lon], 14);
                }});
            }});
        }}

        document.getElementById('all').onclick = () => {{
            DATA.routes.forEach(r => {{
                if (!shown[r.rn]) {{
                    layers[r.rn].addTo(map);
                    shown[r.rn] = true;
                    document.getElementById('row' + r.rn).classList.remove('off');
                }}
            }});
        }};

        document.getElementById('none').onclick = () => {{
            DATA.routes.forEach(r => {{
                if (shown[r.rn]) {{
                    map.removeLayer(layers[r.rn]);
                    shown[r.rn] = false;
                    document.getElementById('row' + r.rn).classList.add('off');
                }}
            }});
        }};

        document.getElementById('toggleUnassigned').onclick = () => {{
            if (unassignedLayer) {{
                if (unassignedVisible) {{
                    map.removeLayer(unassignedLayer);
                }} else {{
                    unassignedLayer.addTo(map);
                }}
                unassignedVisible = !unassignedVisible;
            }}
        }};

        if (document.getElementById('closeUnassigned')) {{
            document.getElementById('closeUnassigned').onclick = () => {{
                const list = document.getElementById('unassignedList');
                list.classList.toggle('collapsed');
            }};
        }}
    </script>
</body>
</html>'''

    return html


# === Streamlit UI ===

st.title("🚚 Vehicle Routing Simulator")
st.caption("Clarke-Wright algorithm with aggressive packing optimization")

# Check if warehouse selected from mapping page
if 'routing_warehouse' not in st.session_state:
    st.error("⚠️ No warehouse selected. Please select a warehouse from the Warehouse Mapping page.")
    if st.button("← Back to Warehouse Mapping"):
        st.switch_page("pages/2_📍_Warehouse_Mapping.py")
    st.stop()

if 'stores' not in st.session_state or not st.session_state.stores:
    st.error("⚠️ No stores loaded. Please go back to Warehouse Mapping.")
    if st.button("← Back to Warehouse Mapping"):
        st.switch_page("pages/2_📍_Warehouse_Mapping.py")
    st.stop()

warehouse = st.session_state.routing_warehouse

# Get stores assigned to this warehouse
warehouse_stores = [
    s for s in st.session_state.stores
    if s.get('assigned_warehouse') == warehouse['id'] and not s.get('removed')
]

if not warehouse_stores:
    st.error(f"⚠️ No stores assigned to {warehouse['name']}")
    if st.button("← Back to Warehouse Mapping"):
        st.switch_page("pages/2_📍_Warehouse_Mapping.py")
    st.stop()

# Auto-fill plant from warehouse
plant_lat = warehouse['lat']
plant_lon = warehouse['lon']
plant_name = warehouse['name']

with st.sidebar:
    st.header("⚙️ Configuration")

    # Show warehouse info (read-only)
    st.info(f"**Warehouse:** {plant_name}  \n**Stores:** {len(warehouse_stores)}  \n**Location:** {plant_lat:.4f}, {plant_lon:.4f}")

    if st.button("← Back to Mapping"):
        st.switch_page("pages/2_📍_Warehouse_Mapping.py")

    st.divider()

    st.subheader("Fleet Configuration")
    num_vehicle_types = st.number_input("Number of Vehicle Types", value=2, min_value=1, max_value=5)

    vehicles = {}
    for i in range(num_vehicle_types):
        with st.expander(f"🚛 Vehicle Type {i+1}", expanded=i==0):
            vtype = st.text_input("Name", value="bada dost" if i==0 else "bolero", key=f"vtype_{i}")
            vcap = st.number_input("Capacity (crates)", value=120 if i==0 else 90, min_value=1, key=f"vcap_{i}")
            vcost = st.number_input("Cost per Vehicle (₹)", value=110000 if i==0 else 95000, min_value=0, key=f"vcost_{i}")
            vcount = st.number_input("Count Available", value=6 if i==0 else 4, min_value=1, key=f"vcount_{i}")
            vehicles[vtype] = {'capacity': vcap, 'cost': vcost, 'count': vcount}

    st.subheader("Routing Constraints")
    col1, col2 = st.columns(2)
    with col1:
        max_util = st.slider("Max Utilization %", 0, 100, 90) / 100
    with col2:
        min_util = st.slider("Min Utilization %", 0, 100, 70) / 100

    if min_util > max_util:
        st.error("⚠️ Min utilization cannot be greater than max utilization")
        min_util = max_util - 0.05
    if max_util == 0:
        st.error("⚠️ Max utilization must be greater than 0")
        max_util = 0.5

    max_stops = st.number_input("Max Stops per Route", value=6, min_value=1, max_value=20)
    max_km = st.number_input("Max Round Trip Distance (km)", value=150, min_value=1)

    st.subheader("Operations")
    start_time = st.time_input("Loading Start Time", value=datetime.strptime("05:00", "%H:%M").time())
    docks = st.number_input("Number of Docks", value=4, min_value=1)
    load_time = st.number_input("Load Time per Vehicle (min)", value=15, min_value=1)
    unload_time = st.number_input("Unload Time per Stop (min)", value=15, min_value=1)
    speed = st.number_input("Avg Speed (km/h)", value=30, min_value=1)
    use_osrm = st.checkbox("Use Real Road Distance (OSRM API)", value=False)

    st.subheader("Delivery Model")
    delivery_model = st.radio(
        "Choose delivery pattern:",
        options=['standard', 'forward_reverse'],
        format_func=lambda x: "Standard (112233): Deliver + Pickup at each stop" if x == 'standard'
                             else "Forward-Reverse (123321): Deliver all, then pickup all",
        index=0
    )

    run = st.button("🚀 Run Simulation", type="primary", use_container_width=True)

if run:
    with st.spinner("Running Clarke-Wright algorithm..."):
        # Convert warehouse stores to expected format
        stores = []
        for s in warehouse_stores:
            stores.append({
                'id': s['id'],
                'name': s['name'],
                'lat': s['lat'],
                'lon': s['lon'],
                'crates': s.get('crates', 0)
            })

        plant = {'lat': plant_lat, 'lon': plant_lon, 'name': plant_name}

        try:
            routes, unassigned, distance_methods = clarke_wright(
                stores, plant, vehicles, max_stops, max_util, min_util, max_km,
                start_time.strftime("%H:%M"), docks, load_time, unload_time, speed, use_osrm, delivery_model
            )
        except ValueError as e:
            st.error(f"❌ Validation Error: {str(e)}")
            st.stop()
        except Exception as e:
            st.error(f"❌ Unexpected Error: {str(e)}")
            st.error("Please check your inputs and try again. If the problem persists, contact support.")
            st.stop()

        # Format delivery model for display
        model_display = "Standard (112233)" if delivery_model == 'standard' else "Forward-Reverse (123321)"

        total_cost = sum(r['cost'] for r in routes)
        total_crates_delivered = sum(r['crates'] for r in routes)
        avg_cost_per_crate = round(total_cost / total_crates_delivered, 2) if total_crates_delivered > 0 else 0

        # Calculate unique stores (not total stops) - important for 123321 model
        unique_stores = len(set(stop['id'] for r in routes for stop in r['stops']))

        output = {
            'plant': plant,
            'kpis': {
                'routes': len(routes),
                'stores': unique_stores,  # Unique stores, not total stops
                'crates': total_crates_delivered,
                'dist': round(sum(r['dist'] for r in routes), 1),
                'unassigned': len(unassigned),
                'total_cost': total_cost,
                'avg_cost_per_crate': avg_cost_per_crate
            },
            'routes': routes,
            'unassigned': [{'id': s['id'], 'name': s['name'], 'crates': s['crates'],
                           'lat': s['lat'], 'lon': s['lon']} for s in unassigned],
            'max_util': int(max_util * 100),
            'distance_method': ' + '.join(sorted(distance_methods)),
            'delivery_model': model_display
        }

        st.session_state.results = {
            'output': output,
            'routes': routes,
            'vehicles': vehicles,
            'distance_method': output['distance_method'],
            'delivery_model': model_display
        }

# Display results from session state
if st.session_state.results:
    output = st.session_state.results['output']
    routes = st.session_state.results['routes']
    vehicles = st.session_state.results['vehicles']
    distance_method = st.session_state.results.get('distance_method', 'Unknown')
    delivery_model = st.session_state.results.get('delivery_model', 'Unknown')

    st.success(f"✓ Generated {len(routes)} routes for {output['kpis']['stores']} stores")
    col_a, col_b = st.columns(2)
    with col_a:
        st.info(f"📏 Distance: **{distance_method}**")
    with col_b:
        st.info(f"🚚 Model: **{delivery_model}**")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Routes", output['kpis']['routes'])
    col2.metric("Stores", output['kpis']['stores'])
    col3.metric("Total Crates", output['kpis']['crates'])
    col4.metric("Total km (RT)", output['kpis']['dist'])
    col5.metric("Unassigned", output['kpis']['unassigned'])

    # Cost metrics
    st.subheader("💰 Cost Analysis")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Fleet Cost", f"₹{output['kpis']['total_cost']:,.0f}")
    col2.metric("Avg Cost/Crate", f"₹{output['kpis']['avg_cost_per_crate']}")
    col3.metric("Cost Efficiency", f"{output['kpis']['avg_cost_per_crate']:.2f}/crate")

    # Fleet usage
    st.subheader("🚛 Fleet Usage")
    fleet_usage = {}
    for r in routes:
        fleet_usage[r['veh']] = fleet_usage.get(r['veh'], 0) + 1

    total_avail = sum(v['count'] for v in vehicles.values())
    cols = st.columns(len(vehicles))
    for i, (vtype, vdata) in enumerate(vehicles.items()):
        used = fleet_usage.get(vtype, 0)
        avg_util = sum(r['util'] for r in routes if r['veh'] == vtype) / max(used, 1)
        cols[i].metric(f"{vtype}", f"{used}/{vdata['count']}", f"{avg_util:.0f}% avg util")

    st.caption(f"📊 Total: {len(routes)}/{total_avail} vehicles · Aggressive packing for target utilization")

    # Route details - show each store only once (skip pickup duplicates in 123321 model)
    st.subheader("📋 Route Details")
    route_df = []
    for r in routes:
        seen_stores = set()  # Track stores already added for this route
        for s in r['stops']:
            # Skip if this store was already added (pickup phase in 123321)
            if s['id'] in seen_stores:
                continue
            seen_stores.add(s['id'])

            # Remove "(Deliver)" or "(Pickup)" suffix from name
            store_name = s['name'].replace(' (Deliver)', '').replace(' (Pickup)', '')

            route_df.append({
                'Route': r['rn'],
                'Vehicle': r['veh'],
                'Seq': s['seq'],
                'Store_ID': s['id'],
                'Store_Name': store_name,
                'Crates': s['crates'],
                'ETA': s['eta'],
                'Dispatch': r['dispatch'],
                'Route_Crates': r['crates'],
                'Vehicle_Cap': r['cap'],
                'Util%': r['util'],
                'RT_Distance_km': r['dist'],
                'Vehicle_Cost': r['cost'],
                'Cost_Per_Crate': r['cost_per_crate']
            })

    st.dataframe(pd.DataFrame(route_df), use_container_width=True, height=400)

    # Downloads
    st.subheader("📥 Download Results")
    col1, col2, col3 = st.columns(3)

    with col1:
        html = generate_html(output)
        st.download_button("⬇️ HTML Map", html, "routes_map.html", "text/html",
                         key="dl_html", use_container_width=True)
    with col2:
        csv_buffer = BytesIO()
        pd.DataFrame(route_df).to_csv(csv_buffer, index=False)
        st.download_button("⬇️ CSV Routes", csv_buffer.getvalue(), "routes.csv", "text/csv",
                         key="dl_csv", use_container_width=True)
    with col3:
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(route_df).to_excel(writer, sheet_name='Routes', index=False)
            if output['unassigned']:
                pd.DataFrame(output['unassigned']).to_excel(writer, sheet_name='Unassigned', index=False)
        st.download_button("⬇️ Excel Full", excel_buffer.getvalue(), "routes.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         key="dl_excel", use_container_width=True)

else:
    st.info("👈 Configure vehicles and parameters, then click 'Run Simulation'")
