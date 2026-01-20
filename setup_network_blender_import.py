import bpy
import json
import os

# === CONFIGURATION ===
JSON_FILE = r'E:\Google Drive Sync Files\My Drive\Art\Blender Files\Experiments & Test-Scenes\Plexus Effect\network_3d.json'
NODE_SIZE = 0.3  # Size of sphere for each node
CREATE_EDGES = True  # Set to False if you only want nodes

FAMILIARITY_MAP = {
    '🏆 Profissional': 4, '💪 Confiante': 3, '📚 Familiar': 2,
    '🌱 Iniciante': 1, '❓ Desconhecida': 0, '': 0
}

def load_network_json(json_path):
    """Load network data from JSON"""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['nodes'], data['edges']

def create_node_object(node_data, collection):
    """Create an individual object for each node with procedural attributes for Geo Nodes"""
    name = node_data['name']
    x, y, z = node_data['x'], node_data['y'], node_data['z']
    
    # Create a small sphere mesh for the node
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=NODE_SIZE,
        location=(x, y, z),
        segments=16,
        ring_count=8
    )
    
    obj = bpy.context.active_object
    obj.name = name
    
    # === IDENTIFIER PROPERTIES ===
    obj["skill_name"] = name
    
    # === NETWORK TOPOLOGY (for spring/repulsion calculations in Geo Nodes) ===
    obj["req_direct"] = int(node_data.get('req_direct', 0))  # Number of skills requiring this
    obj["dep_direct"] = int(node_data.get('dep_direct', 0))  # Number of skills this depends on
    obj["req_indirect"] = float(node_data.get('req_indirect', 0))
    obj["dep_indirect"] = float(node_data.get('dep_indirect', 0))
    
    # === PROCEDURAL METRICS (computed values for Geo Nodes math) ===
    obj["network_centrality"] = float(node_data.get('network_centrality', 
        obj["req_direct"] * obj["dep_direct"]))  # R * D
    obj["foundation_efficiency"] = float(node_data.get('foundation_efficiency',
        obj["req_direct"] / (1 + obj["dep_direct"])))  # R / (1 + D)
    obj["total_connections"] = float(obj["req_direct"] + obj["dep_direct"])
    
    # === QUALITATIVE ATTRIBUTES ===
    obj["familiarity"] = node_data.get('familiarity', '')
    obj["familiarity_num"] = float(FAMILIARITY_MAP.get(node_data.get('familiarity', ''), 0))
    obj["interest"] = node_data.get('interest', '')
    obj["interest_num"] = float(node_data.get('interest_num', 0))
    obj["market"] = node_data.get('market', '')
    obj["market_num"] = float(node_data.get('market_num', 0))
    
    # === SCORING SYSTEMS ===
    obj["req_score"] = float(node_data.get('req_score', 0))
    obj["master_score"] = float(node_data.get('master_score', 0))
    
    # === POSITION DATA (useful for procedural displacement in Geo Nodes) ===
    obj["orig_x"] = float(x)
    obj["orig_y"] = float(y)
    obj["orig_z"] = float(z)
    
    # === INFLUENCE MULTIPLIERS (for spring and repulsion force scaling) ===
    # These can be driven by formulas in Geo Nodes
    obj["req_influence"] = float(node_data.get('req_score', 0)) * 0.1  # Scale requirement importance
    obj["dep_influence"] = float(node_data.get('dep_indirect', 0)) * 0.1  # Scale dependency weight
    obj["spring_multiplier"] = 1.0  # User-adjustable in Geo Nodes
    obj["repulsion_multiplier"] = 1.0  # User-adjustable in Geo Nodes
    
    # Make properties visible in UI with descriptions
    properties_desc = {
        "skill_name": "Skill identifier",
        "req_direct": "Direct dependencies (count)",
        "dep_direct": "Required by (count)",
        "network_centrality": "R × D (hub importance)",
        "foundation_efficiency": "R / (1+D) (foundation quality)",
        "total_connections": "R + D (connectivity)",
        "familiarity_num": "Skill level (0-5)",
        "interest_num": "Personal interest (0-5)",
        "market_num": "Market relevance (0-5)",
        "req_score": "Requirement score from CSV",
        "master_score": "Mastery score from CSV",
        "spring_multiplier": "PROCEDURAL: Spring force multiplier",
        "repulsion_multiplier": "PROCEDURAL: Repulsion force multiplier",
    }
    
    for prop, desc in properties_desc.items():
        if prop in obj:
            obj.id_properties_ui(prop).update(description=desc)
    
    # Move to collection
    for coll in obj.users_collection:
        coll.objects.unlink(obj)
    collection.objects.link(obj)
    
    return obj

def create_edge_curve(source_obj, target_obj, edges_collection):
    """Create a curve connecting two nodes"""
    # Create curve data
    curve_data = bpy.data.curves.new(name=f"{source_obj.name}_to_{target_obj.name}", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.02  # Thickness of the edge
    
    # Create spline
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(1)  # Add one more point (total 2)
    
    # Set start point
    spline.bezier_points[0].co = source_obj.location
    spline.bezier_points[0].handle_left_type = 'AUTO'
    spline.bezier_points[0].handle_right_type = 'AUTO'
    
    # Set end point
    spline.bezier_points[1].co = target_obj.location
    spline.bezier_points[1].handle_left_type = 'AUTO'
    spline.bezier_points[1].handle_right_type = 'AUTO'
    
    # Create object
    curve_obj = bpy.data.objects.new(f"Edge_{source_obj.name}_to_{target_obj.name}", curve_data)
    edges_collection.objects.link(curve_obj)
    
    # Store references
    curve_obj["source"] = source_obj.name
    curve_obj["target"] = target_obj.name
    
    return curve_obj

def clear_scene():
    """Clear default objects"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

# === MAIN ===
if __name__ == '__main__':
    try:
        print("=" * 60)
        print("Creating Individual Node Objects from Network...")
        print("=" * 60)
        
        # Clear scene
        clear_scene()
        
        # Create collections
        nodes_collection = bpy.data.collections.new("Skills_Nodes")
        bpy.context.scene.collection.children.link(nodes_collection)
        
        if CREATE_EDGES:
            edges_collection = bpy.data.collections.new("Skills_Edges")
            bpy.context.scene.collection.children.link(edges_collection)
        
        # Load data
        nodes, edges = load_network_json(JSON_FILE)
        print(f"\nLoaded {len(nodes)} nodes and {len(edges)} edges")
        
        # Create node objects
        print("\nCreating node objects...")
        node_objects = {}
        for i, node in enumerate(nodes):
            obj = create_node_object(node, nodes_collection)
            node_objects[node['name']] = obj
            if (i + 1) % 5 == 0:
                print(f"  Created {i + 1}/{len(nodes)} nodes...")
        
        print(f"✓ Created {len(node_objects)} node objects")
        
        # Create edge curves
        if CREATE_EDGES:
            print("\nCreating edge curves...")
            edge_count = 0
            for edge in edges:
                source_name = edge['source']
                target_name = edge['target']
                
                if source_name in node_objects and target_name in node_objects:
                    create_edge_curve(
                        node_objects[source_name],
                        node_objects[target_name],
                        edges_collection
                    )
                    edge_count += 1
            
            print(f"✓ Created {edge_count} edge curves")
        
        print("\n" + "=" * 60)
        print("SUCCESS! Network imported as individual objects")
        print("=" * 60)
        print("\n📋 PROPERTIES AVAILABLE FOR GEOMETRY NODES:")
        print("\nTOPOLOGY METRICS (for spring/repulsion):")
        print("  • req_direct: Skills that require this one")
        print("  • dep_direct: Skills this one depends on")
        print("  • network_centrality: R × D (hub score)")
        print("  • foundation_efficiency: R / (1+D) (foundation quality)")
        print("\nQUALITATIVE ATTRIBUTES:")
        print("  • familiarity_num: Your skill level (0-5)")
        print("  • interest_num: Your interest level (0-5)")
        print("  • market_num: Market relevance (0-5)")
        print("\nPROCEDURAL CONTROLS (editable in Geo Nodes):")
        print("  • spring_multiplier: 1.0 (adjust for spring force)")
        print("  • repulsion_multiplier: 1.0 (adjust for repulsion force)")
        print("\n💡 HOW TO USE IN GEOMETRY NODES:")
        print("  1. Select a node object (any sphere)")
        print("  2. Expand its Geometry Nodes modifier")
        print("  3. In the node tree, use 'Object Info' node → 'Location'")
        print("  4. Use 'Attribute' nodes to read these properties:")
        print("     - Multiply 'network_centrality' by 'spring_multiplier'")
        print("     - Multiply 'req_direct' by 'repulsion_multiplier'")
        print("  5. Connect these to your plexus spring/repulsion nodes")
        print("  6. You can animate 'spring_multiplier' and 'repulsion_multiplier'")
        print("     to interactively control the network behavior!")
        print("\n🔗 EDGES:")
        print("  All edges stored in 'Skills_Edges' collection (curves)")
        print("  Can be re-created in Geo Nodes using edge data")
        print("\n📁 COLLECTIONS:")
        print(f"  - Skills_Nodes: {len(node_objects)} objects")
        if CREATE_EDGES:
            print(f"  - Skills_Edges: {edge_count} curves")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR:")
        print("=" * 60)
        import traceback
        traceback.print_exc()