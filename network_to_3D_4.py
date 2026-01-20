import csv
import json
import random
import math
import os
import unicodedata
import re

# === CONFIGURATION ===
CSV_FILE = 'skills-data.csv'
OUTPUT_JSON = 'network_3d.json'
OUTPUT_OBJ = 'network_3d.obj'

# Layout algorithm: 'force' or 'sphere' or 'hierarchical'
LAYOUT = 'force'

# Force-directed parameters
ITERATIONS = 100
SPRING_LENGTH = 3.0
REPULSION_STRENGTH = 50.0

def emoji_to_num(emoji_str):
    """Convert emoji to numeric value"""
    if not emoji_str:
        return 0
    
    # Familiarity scale
    fam_map = {
        '🏆 Profissional': 5, '🏆': 5,
        '💪 Confiante': 4, '💪': 4,
        '📚 Familiar': 3, '📚': 3,
        '🌱 Iniciante': 2, '🌱': 2,
        '❓ Desconhecida': 1, '❓': 1
    }
    
    # Interest/Market scale
    int_map = {
        '⭐': 5, '🔥': 4, '👍': 3, '😐': 2, '🤷': 1
    }
    
    emoji_str = str(emoji_str).strip()
    
    if emoji_str in fam_map:
        return fam_map[emoji_str]
    if emoji_str in int_map:
        return int_map[emoji_str]
    
    # Try to extract just the emoji
    for key in fam_map:
        if key in emoji_str:
            return fam_map[key]
    for key in int_map:
        if key in emoji_str:
            return int_map[key]
    
    return 0

def load_network(csv_file):
    """Load nodes and edges from CSV"""
    nodes = {}
    temp_dependencies = {}  # Store deps temporarily
    temp_requirements = {}  # Store reqs temporarily
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = csv_file if os.path.isabs(csv_file) else os.path.join(script_dir, csv_file)
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        def normalize_key(s):
            if s is None:
                return ''
            s = str(s)
            s = unicodedata.normalize('NFKD', s)
            s = ''.join(ch for ch in s if not unicodedata.combining(ch))
            return s.strip().lower()
        
        header_map = {}
        if reader.fieldnames:
            for h in reader.fieldnames:
                header_map[normalize_key(h)] = h
        
        # Find column names
        name_key = (header_map.get(normalize_key('Nome da Área/Habilidade')) or 
                   header_map.get(normalize_key('Nome da Area/Habilidade')))
        
        deps_key = (header_map.get(normalize_key('Depende de...')) or 
                   header_map.get(normalize_key('Depende de')))
        
        reqs_key = (header_map.get(normalize_key('Requerido por...')) or
                   header_map.get(normalize_key('Requerido por')))
        
        fam_key = header_map.get(normalize_key('Grau de Familiaridade'))
        int_key = header_map.get(normalize_key('Interesse'))
        mkt_key = (header_map.get(normalize_key('Relevância no Mercado')) or
                  header_map.get(normalize_key('Relevancia no Mercado')))
        
        # Find score columns
        req_score_key = None
        master_score_key = None
        req_indirect_key = None
        dep_indirect_key = None
        
        for norm_key, actual_key in header_map.items():
            if 'requirement score' in norm_key or 'req score' in norm_key:
                req_score_key = actual_key
            elif 'master' in norm_key and 'score' in norm_key:
                master_score_key = actual_key
            elif 'req' in norm_key and 'indirect' in norm_key:
                req_indirect_key = actual_key
            elif 'dep' in norm_key and 'indirect' in norm_key:
                dep_indirect_key = actual_key
        
        print(f"Column mapping:")
        print(f"  Name: {name_key}")
        print(f"  Dependencies: {deps_key}")
        print(f"  Requirements: {reqs_key}")
        print(f"  Familiarity: {fam_key}")
        print(f"  Interest: {int_key}")
        print(f"  Market: {mkt_key}\n")
        
        for row in reader:
            name = row.get(name_key, '').strip() if name_key else ''
            
            if not name:
                continue
            
            # Get all properties
            fam_raw = row.get(fam_key, '') if fam_key else ''
            int_raw = row.get(int_key, '') if int_key else ''
            mkt_raw = row.get(mkt_key, '') if mkt_key else ''
            
            nodes[name] = {
                'name': name,
                'familiarity': fam_raw,
                'familiarity_num': emoji_to_num(fam_raw),
                'interest': int_raw,
                'interest_num': emoji_to_num(int_raw),
                'market': mkt_raw,
                'market_num': emoji_to_num(mkt_raw),
                'req_score': 0,
                'master_score': 0,
                'req_indirect': 0,
                'dep_indirect': 0,
                'x': random.uniform(-10, 10),
                'y': random.uniform(-10, 10),
                'z': random.uniform(-10, 10)
            }
            
            # Get scores from database if available
            if req_score_key:
                try:
                    nodes[name]['req_score'] = float(row.get(req_score_key, 0) or 0)
                except (ValueError, TypeError):
                    pass
            
            if master_score_key:
                try:
                    nodes[name]['master_score'] = float(row.get(master_score_key, 0) or 0)
                except (ValueError, TypeError):
                    pass
            
            if req_indirect_key:
                try:
                    nodes[name]['req_indirect'] = float(row.get(req_indirect_key, 0) or 0)
                except (ValueError, TypeError):
                    pass
            
            if dep_indirect_key:
                try:
                    nodes[name]['dep_indirect'] = float(row.get(dep_indirect_key, 0) or 0)
                except (ValueError, TypeError):
                    pass
            
            # Store dependencies temporarily
            if deps_key:
                deps_raw = row.get(deps_key, '').strip()
                if deps_raw:
                    temp_dependencies[name] = deps_raw
            
            # Store requirements temporarily
            if reqs_key:
                reqs_raw = row.get(reqs_key, '').strip()
                if reqs_raw:
                    temp_requirements[name] = reqs_raw
    
    # Now create edges after all nodes are loaded
    edges = []
    
    def parse_relations(raw_str):
        """Parse comma-separated relations, handling parentheses"""
        targets = []
        current = ''
        paren_depth = 0
        
        for char in raw_str:
            if char == '(':
                paren_depth += 1
                current += char
            elif char == ')':
                paren_depth -= 1
                current += char
            elif char == ',' and paren_depth == 0:
                if current.strip():
                    targets.append(current.strip())
                current = ''
            else:
                current += char
        
        if current.strip():
            targets.append(current.strip())
        
        # Clean each target by removing URL-encoded filenames
        clean_targets = []
        for target in targets:
            clean_name = re.sub(r'\s+\([^()]*%.*?\.(csv|md)\)\s*$', '', target, flags=re.DOTALL).strip()
            if clean_name:
                clean_targets.append(clean_name)
        
        return clean_targets
    
    # Process dependencies (A depends on B → edge from B to A)
    for source_name, deps_raw in temp_dependencies.items():
        targets = parse_relations(deps_raw)
        for target_name in targets:
            if target_name in nodes:
                edges.append({'source': target_name, 'target': source_name})
            else:
                print(f"Warning: '{source_name}' depends on '{target_name}' but '{target_name}' not found")
    
    # Process requirements (A required by B → edge from A to B)
    for source_name, reqs_raw in temp_requirements.items():
        targets = parse_relations(reqs_raw)
        for target_name in targets:
            if target_name in nodes:
                # Check if edge already exists
                if not any(e['source'] == source_name and e['target'] == target_name for e in edges):
                    edges.append({'source': source_name, 'target': target_name})
            else:
                print(f"Warning: '{source_name}' required by '{target_name}' but '{target_name}' not found")
    
    # Calculate direct counts from edges
    for node in nodes.values():
        node['req_direct'] = sum(1 for e in edges if e['source'] == node['name'])
        node['dep_direct'] = sum(1 for e in edges if e['target'] == node['name'])
    
    return list(nodes.values()), edges

def apply_layout(nodes, edges, layout_type='force'):
    """Apply layout algorithm"""
    if layout_type == 'force':
        for _ in range(ITERATIONS):
            # Repulsion
            for i, n1 in enumerate(nodes):
                fx, fy, fz = 0, 0, 0
                for j, n2 in enumerate(nodes):
                    if i == j:
                        continue
                    dx = n1['x'] - n2['x']
                    dy = n1['y'] - n2['y']
                    dz = n1['z'] - n2['z']
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz) + 0.1
                    force = REPULSION_STRENGTH / (dist * dist)
                    fx += (dx / dist) * force
                    fy += (dy / dist) * force
                    fz += (dz / dist) * force
                
                n1['x'] += fx * 0.01
                n1['y'] += fy * 0.01
                n1['z'] += fz * 0.01
            
            # Spring attraction
            for edge in edges:
                source = next((n for n in nodes if n['name'] == edge['source']), None)
                target = next((n for n in nodes if n['name'] == edge['target']), None)
                if not source or not target:
                    continue
                
                dx = target['x'] - source['x']
                dy = target['y'] - source['y']
                dz = target['z'] - source['z']
                dist = math.sqrt(dx*dx + dy*dy + dz*dz) + 0.1
                force = (dist - SPRING_LENGTH) * 0.1
                
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                fz = (dz / dist) * force
                
                source['x'] += fx
                source['y'] += fy
                source['z'] += fz
                target['x'] -= fx
                target['y'] -= fy
                target['z'] -= fz

def export_json(nodes, edges, output_file):
    """Export as JSON with enhanced procedural data for Blender Geo Nodes"""
    # Pre-calculate metrics for all nodes to enable Geometry Nodes procedures
    for node in nodes:
        # Network topology metrics
        node['network_centrality'] = node['req_direct'] * node['dep_direct']
        node['foundation_efficiency'] = node['req_direct'] / (1 + node['dep_direct'])
        node['total_connections'] = node['req_direct'] + node['dep_direct']
        
        # Derived scores for procedural control
        node['connection_influence'] = (node['req_direct'] * 0.7 + node['dep_direct'] * 0.3) / max(1, max(
            n['req_direct'] for n in nodes if n['req_direct'] > 0
        )) if nodes else 0
    
    data = {
        'nodes': nodes,
        'edges': edges,
        'metadata': {
            'layout': LAYOUT,
            'iterations': ITERATIONS,
            'spring_length': SPRING_LENGTH,
            'repulsion_strength': REPULSION_STRENGTH,
            'total_nodes': len(nodes),
            'total_edges': len(edges)
        }
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✓ Exported {len(nodes)} nodes and {len(edges)} edges to {output_file}")

def export_obj(nodes, edges, output_file):
    """Export as Wavefront OBJ"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Career Skills Network\n")
        f.write(f"# {len(nodes)} nodes, {len(edges)} edges\n\n")
        
        for node in nodes:
            f.write(f"v {node['x']:.6f} {node['y']:.6f} {node['z']:.6f}\n")
        
        f.write("\n")
        
        node_map = {n['name']: i+1 for i, n in enumerate(nodes)}
        for edge in edges:
            src_idx = node_map.get(edge['source'])
            tgt_idx = node_map.get(edge['target'])
            if src_idx and tgt_idx:
                f.write(f"l {src_idx} {tgt_idx}\n")
    
    print(f"✓ Exported to {output_file}")

if __name__ == '__main__':
    print("Loading network...")
    nodes, edges = load_network(CSV_FILE)
    
    print(f"\nApplying {LAYOUT} layout...")
    apply_layout(nodes, edges, LAYOUT)
    
    print(f"\nExporting...")
    export_json(nodes, edges, OUTPUT_JSON)
    export_obj(nodes, edges, OUTPUT_OBJ)
    
    print(f"\n✅ Done! Load {OUTPUT_JSON} in your HTML visualization.")