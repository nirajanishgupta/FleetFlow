"""Page 2: Warehouse Mapping - Assign stores to warehouses with interactive features"""
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.mapping import (
    assign_stores_to_warehouses,
    haversine_distance,
    get_warehouse_stats,
    get_overall_stats
)

st.set_page_config(page_title="Warehouse Mapping", page_icon="📍", layout="wide")

# Color palette for warehouses
WAREHOUSE_COLORS = ['#2563eb', '#16a34a', '#ea580c', '#7c3aed', '#0d9488',
                    '#db2777', '#ca8a04', '#4f46e5', '#059669', '#0891b2']
INFEASIBLE_COLOR = '#dc2626'

# Initialize session state
if 'warehouses' not in st.session_state:
    st.session_state.warehouses = []
if 'stores' not in st.session_state:
    st.session_state.stores = []
if 'wh_counter' not in st.session_state:
    st.session_state.wh_counter = 1
if 'selected_warehouse_id' not in st.session_state:
    st.session_state.selected_warehouse_id = None
if 'selected_store_ids' not in st.session_state:
    st.session_state.selected_store_ids = set()
if 'last_map_click' not in st.session_state:
    st.session_state.last_map_click = None


def add_warehouse(name, lat, lon, radius=75):
    """Add a new warehouse"""
    wh_id = f"wh_{st.session_state.wh_counter}"
    color = WAREHOUSE_COLORS[(st.session_state.wh_counter - 1) % len(WAREHOUSE_COLORS)]

    warehouse = {
        'id': wh_id,
        'name': name,
        'lat': lat,
        'lon': lon,
        'radius': radius,
        'color': color
    }

    st.session_state.warehouses.append(warehouse)
    st.session_state.wh_counter += 1

    # Recompute assignments
    if st.session_state.stores:
        st.session_state.stores = assign_stores_to_warehouses(
            st.session_state.stores,
            st.session_state.warehouses
        )

    return warehouse


def delete_warehouse(wh_id):
    """Delete a warehouse and recompute assignments"""
    st.session_state.warehouses = [w for w in st.session_state.warehouses if w['id'] != wh_id]

    # Unselect if this was selected
    if st.session_state.selected_warehouse_id == wh_id:
        st.session_state.selected_warehouse_id = None

    # Recompute assignments
    if st.session_state.stores:
        st.session_state.stores = assign_stores_to_warehouses(
            st.session_state.stores,
            st.session_state.warehouses
        )


def load_stores_from_csv(uploaded_file):
    """Load stores from CSV file"""
    try:
        df = pd.read_csv(uploaded_file)

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        # Required columns (case-insensitive matching)
        required = {
            'id': ['buyer_outlet_id', 'outlet_id', 'id', 'store_id'],
            'name': ['buyer_outlet_name', 'outlet_name', 'name', 'store_name'],
            'lat': ['outlet_latitude', 'latitude', 'lat'],
            'lon': ['outlet_longitude', 'longitude', 'lon', 'lng'],
        }

        # Find columns
        col_mapping = {}
        for field, candidates in required.items():
            found = None
            for candidate in candidates:
                if candidate in df.columns:
                    found = candidate
                    break
            if not found:
                return None, f"Missing required column for {field}. Tried: {', '.join(candidates)}"
            col_mapping[field] = found

        # Optional: demand/crates
        crates_col = None
        for col in ['demand_crates', 'demand', 'crates']:
            if col in df.columns:
                crates_col = col
                break

        # Parse stores
        stores = []
        for _, row in df.iterrows():
            try:
                store = {
                    'id': str(row[col_mapping['id']]).strip(),
                    'name': str(row[col_mapping['name']]).strip(),
                    'lat': float(row[col_mapping['lat']]),
                    'lon': float(row[col_mapping['lon']]),
                    'crates': int(row[crates_col]) if crates_col and pd.notna(row[crates_col]) else 0,
                    'removed': False,
                }

                # Validate
                if not store['id'] or not store['name']:
                    continue
                if store['lat'] < -90 or store['lat'] > 90:
                    continue
                if store['lon'] < -180 or store['lon'] > 180:
                    continue

                stores.append(store)
            except:
                continue

        if not stores:
            return None, "No valid stores found in CSV"

        return stores, None

    except Exception as e:
        return None, f"Error reading CSV: {str(e)}"


def reassign_store(store_id, new_warehouse_id):
    """Reassign a single store to a different warehouse"""
    for store in st.session_state.stores:
        if store['id'] == store_id:
            if new_warehouse_id is None or new_warehouse_id == 'unassigned':
                store['assigned_warehouse'] = None
                store['assigned_warehouse_name'] = 'Unassigned'
                store['distance_to_warehouse'] = None
            else:
                wh = next((w for w in st.session_state.warehouses if w['id'] == new_warehouse_id), None)
                if wh:
                    dist = haversine_distance(store['lat'], store['lon'], wh['lat'], wh['lon'])
                    store['assigned_warehouse'] = wh['id']
                    store['assigned_warehouse_name'] = wh['name']
                    store['distance_to_warehouse'] = round(dist, 2)
            break


def mark_infeasible(store_ids):
    """Mark stores as infeasible (removed from routing)"""
    for store in st.session_state.stores:
        if store['id'] in store_ids:
            store['removed'] = True
            store['assigned_warehouse'] = None
            store['assigned_warehouse_name'] = 'Infeasible'


def restore_stores(store_ids):
    """Restore infeasible stores"""
    for store in st.session_state.stores:
        if store['id'] in store_ids:
            store['removed'] = False
    # Recompute assignments for restored stores
    st.session_state.stores = assign_stores_to_warehouses(
        st.session_state.stores,
        st.session_state.warehouses
    )


def create_map(warehouses, stores):
    """Create Folium map with warehouses and stores"""
    if not warehouses and not stores:
        m = folium.Map(location=[28.6, 77.2], zoom_start=5)
        return m

    # Calculate center
    all_lats = [w['lat'] for w in warehouses] + [s['lat'] for s in stores if not s.get('removed')]
    all_lons = [w['lon'] for w in warehouses] + [s['lon'] for s in stores if not s.get('removed')]

    if all_lats and all_lons:
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
    else:
        center_lat, center_lon = 28.6, 77.2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=8)

    # ponytail: simplified markers, no popups - add back if these work
    # Add warehouse circles
    for wh in warehouses:
        folium.Circle(
            location=[wh['lat'], wh['lon']],
            radius=wh['radius'] * 1000,
            color=wh['color'],
            fill=True,
            fillColor=wh['color'],
            fillOpacity=0.1,
            weight=2
        ).add_to(m)

        folium.Marker(
            location=[wh['lat'], wh['lon']],
            tooltip=wh['name']  # Simple string tooltip only
        ).add_to(m)

    # Add store markers
    for store in stores:
        if store.get('removed'):
            continue  # Skip removed stores for now

        if store.get('assigned_warehouse'):
            wh = next((w for w in warehouses if w['id'] == store['assigned_warehouse']), None)
            color = wh['color'] if wh else INFEASIBLE_COLOR
        else:
            color = INFEASIBLE_COLOR

        folium.CircleMarker(
            location=[store['lat'], store['lon']],
            radius=5,
            fillColor=color,
            fillOpacity=0.7,
            color='white',
            weight=1,
            tooltip=store['name']  # Simple string tooltip only
        ).add_to(m)

    return m


# ==============================================================================
# MAIN UI
# ==============================================================================

st.title("📍 Warehouse Mapping")
st.caption("Assign stores to warehouses, then proceed to routing")

# Layout
col_left, col_right = st.columns([1, 2], gap="large")

# ==============================================================================
# LEFT COLUMN: Controls
# ==============================================================================
with col_left:
    # Step 1: Upload Stores
    st.subheader("1️⃣ Upload Stores")

    uploaded_file = st.file_uploader("Upload Store CSV", type=['csv'])

    if uploaded_file:
        if st.button("Load Stores", type="primary"):
            stores, error = load_stores_from_csv(uploaded_file)
            if error:
                st.error(f"❌ {error}")
            else:
                st.session_state.stores = stores
                st.session_state.selected_store_ids = set()  # Clear selection
                # Auto-assign if warehouses exist
                if st.session_state.warehouses:
                    st.session_state.stores = assign_stores_to_warehouses(
                        st.session_state.stores,
                        st.session_state.warehouses
                    )
                st.success(f"✅ Loaded {len(stores)} stores")
                st.rerun()

    with st.expander("ℹ️ CSV Format"):
        st.markdown("""
        **Required columns** (case-insensitive):
        - `buyer_outlet_id` or `id`
        - `buyer_outlet_name` or `name`
        - `outlet_latitude` or `latitude`
        - `outlet_longitude` or `longitude`

        **Optional:**
        - `demand_crates` or `crates`
        """)

    st.divider()

    # Step 2: Add Warehouses
    st.subheader("2️⃣ Add Warehouses")

    with st.form("add_warehouse_form"):
        wh_name = st.text_input("Warehouse Name", placeholder="e.g., Delhi Hub")
        col1, col2 = st.columns(2)
        with col1:
            wh_lat = st.number_input("Latitude", value=28.7041, format="%.6f")
        with col2:
            wh_lon = st.number_input("Longitude", value=77.1025, format="%.6f")

        wh_radius = st.slider("Radius (km)", min_value=10, max_value=300, value=75)

        submitted = st.form_submit_button("➕ Add Warehouse", use_container_width=True)

        if submitted:
            if not wh_name.strip():
                st.error("Please provide a warehouse name")
            else:
                add_warehouse(wh_name.strip(), wh_lat, wh_lon, wh_radius)
                st.success(f"✅ Added {wh_name}")
                st.rerun()

    st.divider()

    # Step 3: Manage Warehouses
    if st.session_state.warehouses:
        st.subheader("3️⃣ Manage Warehouses")

        for wh in st.session_state.warehouses:
            stats = get_warehouse_stats(wh['id'], st.session_state.stores)
            is_selected = (wh['id'] == st.session_state.selected_warehouse_id)

            with st.expander(f"📦 {wh['name']}" + (" ✓" if is_selected else ""), expanded=False):
                st.markdown(f"**Stores:** {stats['total_stores']} | **Crates:** {stats['total_crates']}")

                # Edit radius
                new_radius = st.slider(
                    "Radius (km)",
                    min_value=10,
                    max_value=300,
                    value=wh['radius'],
                    key=f"radius_{wh['id']}"
                )

                if new_radius != wh['radius']:
                    wh['radius'] = new_radius
                    if st.session_state.stores:
                        st.session_state.stores = assign_stores_to_warehouses(
                            st.session_state.stores,
                            st.session_state.warehouses
                        )
                    st.rerun()

                # Route button
                if st.button(f"Route →", key=f"route_{wh['id']}", use_container_width=True, type="primary"):
                    # Store selected warehouse for routing
                    st.session_state.routing_warehouse = wh
                    st.switch_page("pages/3_🚚_Multi_Warehouse_Routing.py")

                # Delete button
                if st.button(f"🗑️ Delete", key=f"del_{wh['id']}", use_container_width=True):
                    delete_warehouse(wh['id'])
                    st.rerun()

    st.divider()

    # Step 4: Statistics
    if st.session_state.stores:
        st.subheader("📊 Statistics")

        stats = get_overall_stats(st.session_state.stores)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total", stats['total'])
        col2.metric("Assigned", stats['assigned'])
        col3.metric("Infeasible", len([s for s in st.session_state.stores if s.get('removed')]))

# ==============================================================================
# RIGHT COLUMN: Map & Table
# ==============================================================================
with col_right:
    st.subheader("🗺️ Visualization")

    if not st.session_state.warehouses and not st.session_state.stores:
        st.info("👈 Upload stores and add warehouses to see the map")
        map_data = None
    else:
        # Create and display map
        m = create_map(st.session_state.warehouses, st.session_state.stores)
        map_data = st_folium(m, width=None, height=500, key="main_map")
   # Create and display map
    
    # Handle map clicks - toggle selection (only process NEW clicks)
    if map_data and map_data.get('last_object_clicked'):
        clicked_lat = map_data['last_object_clicked']['lat']
        clicked_lng = map_data['last_object_clicked']['lng']
        click_signature = f"{clicked_lat:.6f},{clicked_lng:.6f}"

        # Only process if this is a NEW click (not the same as last time)
        if click_signature != st.session_state.last_map_click:
            st.session_state.last_map_click = click_signature

            # Find the clicked store
            clicked_store = None
            for s in st.session_state.stores:
                if abs(s['lat'] - clicked_lat) < 0.0001 and abs(s['lon'] - clicked_lng) < 0.0001:
                    clicked_store = s
                    break

            if clicked_store:
                # Toggle selection
                if clicked_store['id'] in st.session_state.selected_store_ids:
                    st.session_state.selected_store_ids.remove(clicked_store['id'])
                else:
                    st.session_state.selected_store_ids.add(clicked_store['id'])
                st.rerun()

    # Legend
    if st.session_state.warehouses:
        st.markdown("**Legend:**")
        cols = st.columns(min(4, len(st.session_state.warehouses)))
        for i, wh in enumerate(st.session_state.warehouses):
            with cols[i % 4]:
                st.markdown(
                    f'<span style="color:{wh["color"]}">⬤</span> {wh["name"]}',
                    unsafe_allow_html=True
                )
        st.markdown(f'<span style="color:{INFEASIBLE_COLOR}">⬤</span> Unassigned/Infeasible', unsafe_allow_html=True)

    # Interactive table with inline reassignment
    if st.session_state.stores:
        st.markdown("---")
        st.subheader("📋 Store Management")

        # Quick selection buttons
        st.markdown("**Quick Select:**")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("All Stores", use_container_width=True):
                st.session_state.selected_store_ids = set(s['id'] for s in st.session_state.stores if not s.get('removed'))
                st.rerun()

        with col2:
            if st.button("Unassigned", use_container_width=True):
                st.session_state.selected_store_ids = set(
                    s['id'] for s in st.session_state.stores
                    if not s.get('assigned_warehouse') and not s.get('removed')
                )
                st.rerun()

        with col3:
            if st.button("Infeasible", use_container_width=True):
                st.session_state.selected_store_ids = set(s['id'] for s in st.session_state.stores if s.get('removed'))
                st.rerun()

        with col4:
            if st.button("Clear", use_container_width=True):
                st.session_state.selected_store_ids = set()
                st.rerun()

        st.markdown("")  # Spacer

        # Group stores by warehouse
        # Show separate table for each warehouse
        for wh in st.session_state.warehouses:
            wh_stores = [s for s in st.session_state.stores
                        if s.get('assigned_warehouse') == wh['id'] and not s.get('removed')]

            if not wh_stores:
                continue

            st.markdown(f"### 📦 {wh['name']}")
            st.caption(f"{len(wh_stores)} stores · {sum(s.get('crates', 0) for s in wh_stores)} crates")

            table_data = []
            for s in wh_stores:
                table_data.append({
                    'Select': s['id'] in st.session_state.selected_store_ids,
                    'ID': s['id'],
                    'Name': s['name'],
                    'Crates': s.get('crates', 0),
                    'Distance (km)': s.get('distance_to_warehouse', 'N/A'),
                    '_store_id': s['id']
                })

            df = pd.DataFrame(table_data)

            edited_df = st.data_editor(
                df.drop('_store_id', axis=1),
                use_container_width=True,
                hide_index=True,
                height=min(300, len(wh_stores) * 35 + 50),
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select stores",
                        default=False
                    )
                },
                disabled=["ID", "Name", "Crates", "Distance (km)"],
                key=f"table_{wh['id']}"
            )

            # Update selection
            for idx, row in edited_df.iterrows():
                store_id = df.iloc[idx]['_store_id']
                if row['Select']:
                    st.session_state.selected_store_ids.add(store_id)
                else:
                    st.session_state.selected_store_ids.discard(store_id)

            st.markdown("")  # Spacer

        # Unassigned stores
        unassigned_stores = [s for s in st.session_state.stores
                            if not s.get('assigned_warehouse') and not s.get('removed')]

        if unassigned_stores:
            st.markdown(f"### ⚠️ Unassigned Stores")
            st.caption(f"{len(unassigned_stores)} stores · {sum(s.get('crates', 0) for s in unassigned_stores)} crates")

            table_data = []
            for s in unassigned_stores:
                table_data.append({
                    'Select': s['id'] in st.session_state.selected_store_ids,
                    'ID': s['id'],
                    'Name': s['name'],
                    'Crates': s.get('crates', 0),
                    '_store_id': s['id']
                })

            df = pd.DataFrame(table_data)

            edited_df = st.data_editor(
                df.drop('_store_id', axis=1),
                use_container_width=True,
                hide_index=True,
                height=min(300, len(unassigned_stores) * 35 + 50),
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select stores",
                        default=False
                    )
                },
                disabled=["ID", "Name", "Crates"],
                key="table_unassigned"
            )

            for idx, row in edited_df.iterrows():
                store_id = df.iloc[idx]['_store_id']
                if row['Select']:
                    st.session_state.selected_store_ids.add(store_id)
                else:
                    st.session_state.selected_store_ids.discard(store_id)

            st.markdown("")

        # Infeasible stores
        infeasible_stores = [s for s in st.session_state.stores if s.get('removed')]

        if infeasible_stores:
            st.markdown(f"### 🚫 Infeasible Stores")
            st.caption(f"{len(infeasible_stores)} stores · {sum(s.get('crates', 0) for s in infeasible_stores)} crates")

            table_data = []
            for s in infeasible_stores:
                table_data.append({
                    'Select': s['id'] in st.session_state.selected_store_ids,
                    'ID': s['id'],
                    'Name': s['name'],
                    'Crates': s.get('crates', 0),
                    '_store_id': s['id']
                })

            df = pd.DataFrame(table_data)

            edited_df = st.data_editor(
                df.drop('_store_id', axis=1),
                use_container_width=True,
                hide_index=True,
                height=min(300, len(infeasible_stores) * 35 + 50),
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select stores",
                        default=False
                    )
                },
                disabled=["ID", "Name", "Crates"],
                key="table_infeasible"
            )

            for idx, row in edited_df.iterrows():
                store_id = df.iloc[idx]['_store_id']
                if row['Select']:
                    st.session_state.selected_store_ids.add(store_id)
                else:
                    st.session_state.selected_store_ids.discard(store_id)

        # Show bulk actions if stores are selected
        if st.session_state.selected_store_ids:
            st.markdown("---")
            st.markdown(f"**✓ {len(st.session_state.selected_store_ids)} stores selected**")

            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                # Warehouse selector
                wh_options = {'unassigned': 'Unassigned'}
                wh_options.update({wh['id']: wh['name'] for wh in st.session_state.warehouses})

                new_wh = st.selectbox(
                    "Reassign to:",
                    options=list(wh_options.keys()),
                    format_func=lambda x: wh_options[x],
                    key="bulk_wh_select"
                )

            with col2:
                if st.button("✓ Reassign", use_container_width=True, type="primary"):
                    for sid in st.session_state.selected_store_ids:
                        reassign_store(sid, new_wh)
                    st.success(f"✅ Reassigned {len(st.session_state.selected_store_ids)} stores")
                    st.session_state.selected_store_ids = set()
                    st.rerun()

            with col3:
                # Check if selected stores are infeasible or active
                selected_stores = [s for s in st.session_state.stores if s['id'] in st.session_state.selected_store_ids]
                any_infeasible = any(s.get('removed') for s in selected_stores)

                if any_infeasible:
                    if st.button("↻ Restore", use_container_width=True):
                        restore_stores(list(st.session_state.selected_store_ids))
                        st.success(f"✅ Restored {len(st.session_state.selected_store_ids)} stores")
                        st.session_state.selected_store_ids = set()
                        st.rerun()
                else:
                    if st.button("✗ Infeasible", use_container_width=True):
                        mark_infeasible(list(st.session_state.selected_store_ids))
                        st.success(f"✅ Marked {len(st.session_state.selected_store_ids)} as infeasible")
                        st.session_state.selected_store_ids = set()
                        st.rerun()

            if st.button("Clear Selection"):
                st.session_state.selected_store_ids = set()
                st.rerun()
