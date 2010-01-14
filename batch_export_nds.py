
if __name__ == "__main__" :
	print("I'm running from command-line ;) ...")
#	print( dir(bpy.ops.export.nds.get_rna().bl_rna.functions) )
	print( "Blender File : %s" % bpy.context.main.filename )

   
	import sys
	
	script_args_index = sys.argv.index('--')
	print(sys.argv)
	if ( len( sys.argv[script_args_index] ) > 1 ) :
		script_args = sys.argv[script_args_index+1:]
	else :
		script_args = []


	from optparse import OptionParser
	prog_usage = "usage: blender -b blend_file -P %prog -- [script_options]"
	prog_name = "path/to/batch_export_nds.py"
	parser = OptionParser(usage=prog_usage,prog=prog_name)

	parser.add_option("-q", "--quiet",
						action="store_false", dest="verbose", default=True,
						help="don't print status messages to stdout")

	parser.add_option("-l", "--list",
						action="store_const" ,const="list" , dest="command",
						help="List all meshes")

	parser.add_option("-m" , "--mesh",
						action="store" , type="string" , dest="meshes", default="all",
						help="Select one or more meshes to export") 

	parser.add_option("-t" , "--text",
						action="store_const", dest="format", const="TEXT", default="BINARY",
						help="Export CallList in a C source file (.c and .h)")

	parser.add_option("" , "--no-uvs",
						action="store_false", dest="export_uvs", default=True,
						help="Do not export Texture UV coordinates")

	parser.add_option("" , "--no-colors",
						action="store_false", dest="export_colors", default=True,
						help="Do not export Vertex Colors")

	parser.add_option("" , "--no-normals",
						action="store_false" , dest="export_normals", default=True,
						help="Do not export Vertex Normals")

	parser.add_option("" , "--no-armature",
						action="store_false" , dest="export_armature", default=True,
						help="Do not export Vertex Normals")
	

	(prog_options, prog_args) = parser.parse_args(script_args)
	print(prog_options , prog_args)

	if (prog_options.command == 'list'):
		print("List all available meshes")
		for m in bpy.data.meshes :
			print(m.name)
	else :
		bpy.ops.export.nds_calllist(directory="./", meshes=prog_options.meshes , export_uvs=prog_options.export_uvs , export_normals=prog_options.export_normals, export_colors = prog_options.export_colors , export_armature=prog_options.export_armature , file_format=prog_options.format)
