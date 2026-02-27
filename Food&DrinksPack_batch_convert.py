import bpy
import os

# --- PATHS FOR FOOD PACK ---
source_dir = r"C:\Users\Windows10_new\Downloads\Food&DrinksPack"
target_dir = r"C:\Users\Windows10_new\Downloads\Food&DrinksPack_glb"

def get_all_texture_files(start_folder, type_keywords):
    matches = []
    for current_root, dirs, files in os.walk(start_folder):
        for f in files:
            f_lower = f.lower()
            if f_lower.endswith(('.png', '.jpg', '.jpeg', '.tga', '.tif')):
                if any(tk in f_lower for tk in type_keywords):
                    matches.append(os.path.join(current_root, f))
    matches.sort() # Sort alphabetically so we have a consistent order
    return matches

def get_texture_file(start_folder, type_keywords):
    for current_root, dirs, files in os.walk(start_folder):
        for f in files:
            f_lower = f.lower()
            if f_lower.endswith(('.png', '.jpg', '.jpeg', '.tga', '.tif')):
                if any(tk in f_lower for tk in type_keywords):
                    return os.path.join(current_root, f)
    return None

for root, dirs, files in os.walk(source_dir):
    for file in files:
        if file.lower().endswith('.fbx'):
            fbx_path = os.path.join(root, file)
            item_name = os.path.splitext(file)[0]
            
            rel_path = os.path.relpath(root, source_dir)
            out_folder = os.path.join(target_dir, rel_path)
            os.makedirs(out_folder, exist_ok=True)
            
            print(f"\n--- Processing: {file} ---")
            
            # Find ALL base colors 
            t_bases = get_all_texture_files(root, ['base_color', 'base_colo', 'albedo'])
            
            # Find SHARED maps
            t_metal = get_texture_file(root, ['metallic', 'metal'])
            t_rough = get_texture_file(root, ['roughness', 'rough'])
            t_norm = get_texture_file(root, ['normal', 'norm'])
            t_opac = get_texture_file(root, ['opacity', 'alpha'])

            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=fbx_path)

            # Get all meshes and sort them (e.g., Mesh, Mesh.001, Mesh.002)
            meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
            meshes.sort(key=lambda obj: obj.name)

            num_variations = len(t_bases)

            # Loop through each individual mesh in the scene
            for index, obj in enumerate(meshes):
                
                # Pair the mesh with a base color
                if num_variations > 0:
                    current_t_base = t_bases[index % num_variations]
                    # Extract a clean name (e.g., "Beans" from "Beans_Base_Color.png")
                    base_filename = os.path.basename(current_t_base)
                    variation_name = base_filename.split('_')[0]
                    glb_filename = f"{item_name}_{variation_name}.glb"
                else:
                    current_t_base = None
                    glb_filename = f"{item_name}_{index}.glb"

                glb_path = os.path.join(out_folder, glb_filename)
                
                # Deselect everything, then select ONLY the current mesh
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)

                # Move the object to the center (0,0,0) so it's not offset in your game engine
                obj.location = (0, 0, 0)

                # Create the material
                mat = bpy.data.materials.new(name=f"{item_name}_{index}_Mat")
                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                links = mat.node_tree.links
                nodes.clear()
                
                bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
                bsdf.location = (0, 0)
                output = nodes.new(type='ShaderNodeOutputMaterial')
                output.location = (300, 0)
                links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
                
                def add_texture(filepath, color_space, loc, link_input):
                    if filepath and os.path.exists(filepath):
                        filename = os.path.basename(filepath)
                        if filename in bpy.data.images:
                            img = bpy.data.images[filename]
                        else:
                            img = bpy.data.images.load(filepath)
                            
                        img.colorspace_settings.name = color_space
                        node = nodes.new('ShaderNodeTexImage')
                        node.image = img
                        node.location = loc
                        
                        if link_input == 'Emission Color' and 'Emission Color' not in bsdf.inputs:
                            link_input = 'Emission'
                        if link_input in bsdf.inputs:
                            links.new(node.outputs['Color'], bsdf.inputs[link_input])
                        return node
                    return None

                add_texture(current_t_base, 'sRGB', (-300, 200), 'Base Color')
                add_texture(t_rough, 'Non-Color', (-300, -300), 'Roughness')

                if t_metal and os.path.exists(t_metal):
                    add_texture(t_metal, 'Non-Color', (-300, -50), 'Metallic')
                else:
                    if 'Metallic' in bsdf.inputs:
                        bsdf.inputs['Metallic'].default_value = 0.0

                if t_opac and os.path.exists(t_opac):
                    add_texture(t_opac, 'Non-Color', (-300, -450), 'Alpha')
                    mat.blend_method = 'BLEND' 

                if t_norm and os.path.exists(t_norm):
                    filename = os.path.basename(t_norm)
                    if filename in bpy.data.images:
                        img = bpy.data.images[filename]
                    else:
                        img = bpy.data.images.load(t_norm)
                    img.colorspace_settings.name = 'Non-Color'
                    
                    tex_node = nodes.new('ShaderNodeTexImage')
                    tex_node.image = img
                    tex_node.location = (-800, -600)
                    norm_node = nodes.new('ShaderNodeNormalMap')
                    norm_node.location = (100, -600)

                    if 'directx' in filename.lower():
                        sep_rgb = nodes.new('ShaderNodeSeparateColor')
                        sep_rgb.location = (-500, -550)
                        links.new(tex_node.outputs['Color'], sep_rgb.inputs['Color'])

                        invert = nodes.new('ShaderNodeMath')
                        invert.operation = 'SUBTRACT'
                        invert.inputs[0].default_value = 1.0
                        invert.location = (-300, -600)
                        links.new(sep_rgb.outputs['Green'], invert.inputs[1])

                        comb_rgb = nodes.new('ShaderNodeCombineColor')
                        comb_rgb.location = (-100, -550)
                        links.new(sep_rgb.outputs['Red'], comb_rgb.inputs['Red'])
                        links.new(invert.outputs['Value'], comb_rgb.inputs['Green'])
                        links.new(sep_rgb.outputs['Blue'], comb_rgb.inputs['Blue'])
                        
                        links.new(comb_rgb.outputs['Color'], norm_node.inputs['Color'])
                    else:
                        links.new(tex_node.outputs['Color'], norm_node.inputs['Color'])

                    links.new(norm_node.outputs['Normal'], bsdf.inputs['Normal'])

                # Assign material to the isolated object
                obj.data.materials.clear() 
                obj.data.materials.append(mat) 

                # THE FIX: Export ONLY the selected object
                bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=True)
                print(f"Exported individual item: {glb_filename}")

print("\nSPLIT & EXPORT BATCH CONVERSION COMPLETE!")