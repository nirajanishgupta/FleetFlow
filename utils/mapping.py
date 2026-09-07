"""Warehouse-to-store mapping utilities"""
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in km"""
    R = 6371.0088  # Earth radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def assign_stores_to_warehouses(stores, warehouses):
    """
    Assign each store to nearest warehouse within radius.

    Returns:
        stores: Updated store list with 'assigned_warehouse' field
    """
    for store in stores:
        best_warehouse = None
        min_distance = float('inf')

        for warehouse in warehouses:
            dist = haversine_distance(
                store['lat'], store['lon'],
                warehouse['lat'], warehouse['lon']
            )

            # Check if within radius and closer than current best
            if dist <= warehouse['radius'] and dist < min_distance:
                min_distance = dist
                best_warehouse = warehouse

        if best_warehouse:
            store['assigned_warehouse'] = best_warehouse['id']
            store['assigned_warehouse_name'] = best_warehouse['name']
            store['distance_to_warehouse'] = round(min_distance, 2)
        else:
            store['assigned_warehouse'] = None
            store['assigned_warehouse_name'] = 'Unassigned'
            store['distance_to_warehouse'] = None

    return stores


def get_warehouse_stats(warehouse_id, stores):
    """Get statistics for a specific warehouse"""
    assigned = [s for s in stores
                if s.get('assigned_warehouse') == warehouse_id
                and not s.get('removed')]

    total_stores = len(assigned)
    total_crates = sum(s.get('crates', 0) for s in assigned)

    return {
        'total_stores': total_stores,
        'total_crates': total_crates
    }


def get_overall_stats(stores):
    """Get overall assignment statistics"""
    total = len([s for s in stores if not s.get('removed')])
    assigned = len([s for s in stores
                    if s.get('assigned_warehouse')
                    and not s.get('removed')])
    unassigned = total - assigned

    return {
        'total': total,
        'assigned': assigned,
        'unassigned': unassigned
    }
