# coding: utf-8
#
#	Nintendo DS CallList Exporter for Blender
#	Copyright (C) 2008, 2009 Kevin Roy <kiniou_AT_gmail_DOT_com>
#
#	Nintendo DS CallList Exporter for Blender is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

__author__ = ["Kevin (KiNiOu) ROY"]
__url__ = ("www.blender.org", "http://blog.knokorpo.fr")
__version__ = "0.2"

__bpydoc__ = """\
This script export models in Nintendo DS CallList for
the DevKitPro SDK in a .h or .bin file .

Usage:
Go to Export->NintendoDS CallList .
"""

import struct
import array
import ctypes 
import io

import bpy
import random
import math

import binascii

# Define libnds binary functions and macros

def floattov16(n) :
	return ( int(n*(1<<12)) )

def VERTEX_PACK(x,y) :
	return ( struct.pack('<hh', x , y) )
	

def floattov10(n) :
	if (n>.998) :
		return int(0x1FF)
	else :
		return int( n * (1<<9))

def NORMAL_PACK(x,y,z) :
	s = struct.pack('<l' , (x & 0x3FF) | ((y & 0x3FF) << 10) | (z << 20))
	return s

def floattot16(n) :
	#return int( n * (1 << 4) )
	return int(n * (1 << 4))

def TEXTURE_PACK(u,v) :
	#return array.array( (u & 0xFFFF) | (v << 16) , Int32)
	s= struct.pack('<i', (u & 0xFFFF) | (v << 16) )
	return s

def RGB15(r,g,b) :
	#return array.array(r | (g << 5) | (b <<10 ) , Int32)
	s=struct.pack( '<i', r | (g << 5) | (b << 10) )
	return s

FIFO_VERTEX16  = 0x23
FIFO_NORMAL	= 0x21
FIFO_TEX_COORD = 0x22
FIFO_COLOR	 = 0x20
FIFO_NOP	   = 0x00
FIFO_BEGIN	 = 0x40
FIFO_END	   = 0x41

GL_GLBEGIN_ENUM = {
	'GL_TRIANGLES'		: 0 ,
	'GL_QUADS'			: 1 ,
	'GL_TRIANGLE_STRIP' : 2 ,
	'GL_QUAD_STRIP'		: 3 ,
	'GL_TRIANGLE'		: 0 ,
	'GL_QUAD'			: 1
}

DEFAULT_OPTIONS = {
#	'FORMAT'		: 'TEXT',
	'FORMAT'		: 'BINARY',
	'UV'			: True,
	'COLOR'			: True,
	'NORMAL'		: True,
	'ARMATURE'		: True,
}

# a _mesh_option represents export options in the gui
class _mesh_options (object) :
	__slots__ = 'format' , 'uv_export' ,'texfile_export' , 'normals_export' , 'color_export' , 'armature_export', 'mesh_data' , 'mesh_name', 'texture_data' , 'texture_list' , 'texture_w' , 'texture_h', 'dir_path'

	def __init__(self,mesh_data,dir_path, export_uvs , export_colors , export_normals , export_armature, file_format) :
		self.format		 = file_format   #Which format for the export? (if binary is False then a simple .h will be saved)
		self.uv_export	  = export_uvs	#Do we export uv coordinates?
		self.normals_export = export_normals		 #Do we export normals coordinates ?
		self.color_export   = export_colors		  #Do we export color attributes ?
		self.armature_export = export_armature

		self.mesh_data = mesh_data #The Blender Mesh data
		self.mesh_name = mesh_data.name #The Blender Mesh name
		self.texture_w = 0
		self.texture_h = 0
		self.list_textures() #Retrieve all texture bound to the Blender mesh
#		print(self.mesh_data)
#		print(self.mesh_data.uv_textures)
#		print(dir(self.mesh_data))
		
		if ( not self.mesh_data.active_uv_texture ): self.uv_export = False
		if ( not self.mesh_data.vertex_colors ) : self.color_export = False
		
		self.dir_path = dir_path
		self.texfile_export = 0
		

	def list_textures(self) :
		print("listing textures for mesh \"%s\"" % self.mesh_name)
		materials = self.mesh_data.materials
		self.texture_data = []
		#Here we take the first material in the mesh
		tex = []
		if len(materials)>0 :
			tex = materials[0].textures

		self.texture_list = []
		#Here we take the first Texture of Image Type
		img_found = 0
		if len(tex)>0 :
			for t in tex :
				if t != None :
					if (type(t.texture) == bpy.types.ImageTexture and t.texture.image != None) :
						image = t.texture.image
						self.texture_list.append(t)
						#TODO : When image size will be accessible
						img_found = 1

						#print "%s %dx%d" % (image.getName(),image.getSize()[0],image.getSize()[1])

		if (img_found == 1):
			image = self.texture_list[0].texture.image
			self.texture_data.append(image)

			w = 0
			h = 0
			w = image.size[0]
			h = image.size[1]
			ratio = float(w)/float(h)
			print("Texture %s %dx%d ratio=%f" % (image.name,w,h,ratio))

			if (w > 128) : w = 128
			if (w < 8) : w = 8

			if (h > 128) : h = 128
			if (h < 8) : h = 8

			if (ratio < 1.0) :
				w = h * (1/round(1/ratio))
				print("ratio <  1 : Texture %s %dx%d" % (image.name,w,h))
			else :
				h = w / round(ratio)
				print("ratio >= 1 :Texture %s %dx%d" % (image.name,w,h))

			self.texture_w = int(w)
			self.texture_h = int(h)
		else :
			print("!!!Warning : Cannot find any textures bound to the mesh!!!")
			print("!!!		  TEXTURE_PACKs won't be exported		   !!!")

	def get_final_path_mesh(self):
		return ("%s%s" % ( self.dir_path,self.mesh_name) )

	def get_final_path_tex(self):
		return( "%s%s%s" % (self.dir_path , self.mesh_name , ".pcx") )

	def __str__(self):
		return "File Format:%s , Exporting Texture:%s , Exporting Normals:%s , Exporting Colors:%s" % (self.format,self.uv_export,self.normals_export,self.color_export)


class _nds_cmdpack_nop(object) :
	__slots__ = 'cmd','val'

	def __init__(self):
		self.cmd = {}
		self.cmd['TEXT'] = "FIFO_NOP"
		self.cmd['BINARY'] = struct.pack( 'b' , FIFO_NOP )


		self.val = {}
		self.val['TEXT'] = None
		self.val['BINARY'] = None

	def get_cmd(self,format):
		return ( self.cmd[format] )

	def get_val(self,format):
		return ( self.val[format] )

	def get_nb_val(self):
		return ( 0 )

	def __str__(self):
		return ( "%s , %s" % ( self.cmd['TEXT'], self.val['TEXT']) )

class _nds_cmdpack_begin (object) :
	__slots__ = 'cmd','val'

	def __init__(self,begin_opt):
		self.cmd = {}
		self.cmd['TEXT'] = "FIFO_BEGIN"
		self.cmd['BINARY'] = struct.pack( 'b' , FIFO_BEGIN )


		self.val = {}
		self.val['TEXT'] = begin_opt
		self.val['BINARY'] = struct.pack('<i' , GL_GLBEGIN_ENUM[begin_opt] )


	def get_cmd(self,format):
		return ( self.cmd[format] )

	def get_val(self,format):
		return ( self.val[format] )

	def get_nb_val(self):
		return ( 1 )

	def __str__(self):
		return ( "%s , %s" % ( self.cmd['TEXT'], self.val['TEXT']) )

class _nds_cmdpack_end(object) :

	__slots__ = 'cmd','val'

	def __init__(self):
		self.cmd = {}
		self.cmd['TEXT'] = "FIFO_END"
		self.cmd['BINARY'] = struct.pack( 'b' , FIFO_END )


		self.val = {}
		self.val['TEXT'] = None
		self.val['BINARY'] = None


	def get_cmd(self,format):
		return ( self.cmd[format] )

	def get_val(self,format):
		return ( self.val[format] )

	def get_nb_val(self):
		return ( 0 )

	def __str__(self):
		return ( "%s , %s" % ( self.cmd['TEXT'], self.val['TEXT']) )


class _nds_cmdpack_vertex (object) :
	__slots__ = 'cmd','val'

	def __init__(self,vertex=(0.0,0.0,0.0)):
		x, y, z = vertex
		self.cmd = {}
		self.cmd['TEXT'] = "FIFO_VERTEX16"
		self.cmd['BINARY'] = struct.pack( 'b' , FIFO_VERTEX16 )


		self.val = {}
		self.val['TEXT'] = "VERTEX_PACK(floattov16(%f),floattov16(%f)) , VERTEX_PACK(floattov16(%f),0)" % (x,y,z)
		self.val['BINARY'] = VERTEX_PACK(floattov16(x) , floattov16(y)) + VERTEX_PACK(floattov16(z) , floattov16(0))


	def get_cmd(self, format):
		return ( self.cmd[format] )

	def get_val(self, format):
		return ( self.val[format] )

	def get_nb_val(self):
		return ( 2 )

	def __str__(self):
		return ( "%s , %s" % ( self.cmd['TEXT'], self.val['TEXT']) )


class _nds_cmdpack_normal (object):
	__slots__ = 'cmd','val'

	def __init__(self,normal=(0.0,0.0,0.0)):
		x, y, z = normal
		self.cmd = {}
		self.cmd['TEXT'] = "FIFO_NORMAL"
		self.cmd['BINARY'] = struct.pack( 'b' , FIFO_NORMAL )


		self.val = {}
		self.val['TEXT'] =  "NORMAL_PACK(floattov10(%3.6f),floattov10(%3.6f),floattov10(%3.6f))" % (x,y,z)
		self.val['BINARY'] = NORMAL_PACK(floattov10(x) , floattov10(y) , floattov10(z))


	def get_cmd(self, format):
		return ( self.cmd[format] )

	def get_val(self, format):
		return ( self.val[format] )

	def get_nb_val(self):
		return ( 1 )

	def __str__(self):
		return ( "%s , %s" % ( self.cmd['TEXT'], self.val['TEXT']) )

class _nds_cmdpack_color (object):
	__slots__ = 'cmd' , 'val'

	def __init__(self,color=(0,0,0)):
		r,g,b = color
		self.cmd = {}
		self.cmd['TEXT'] = "FIFO_COLOR"
		self.cmd['BINARY'] = struct.pack( 'b' , FIFO_COLOR )


		self.val = {}
		self.val['TEXT'] =  "RGB15(%d,%d,%d)" % (r,g,b)
		self.val['BINARY'] = RGB15(r,g,b)


	def get_cmd(self, format):
		return ( self.cmd[format] )

	def get_val(self, format):
		return ( self.val[format] )

	def get_nb_val(self):
		return ( 1 )

	def __str__(self):
		return ( "%s , %s" % ( self.cmd['TEXT'], self.val['TEXT']) )


class _nds_cmdpack_texture (object):
	__slots__ = 'cmd' , 'val'

	def __init__(self,uv=(0.0,0.0)):
		u,v = uv
		self.cmd = {}
		self.cmd['TEXT'] = "FIFO_TEX_COORD"
		self.cmd['BINARY'] = struct.pack( 'b' , FIFO_TEX_COORD )


		self.val = {}
		self.val['TEXT'] =  "TEXTURE_PACK(floattot16(%3.6f),floattot16(%3.6f))" % (u,v)
		self.val['BINARY'] = TEXTURE_PACK( floattot16(u) , floattot16(v) )


	def get_cmd(self, format):
		return ( self.cmd[format] )

	def get_val(self, format):
		return ( self.val[format] )

	def get_nb_val(self):
		return ( 1 )

	def __str__(self):
		return ( "%s , %s" % ( self.cmd['TEXT'], self.val['TEXT']) )


class _nds_mesh_vertex (object):
	__slots__ = 'vertex','uv','normal','color'

	def __init__(self):
		self.vertex = None
		self.uv = None
		self.normal = None
		self.color = None

	def __str__(self):
		return "MESH_VERTEX(vertex=%s uv=%s normal=%s color=%s)" % (self.vertex , self.uv , self.normal , self.color)


class _nds_cmdpack (object) :
	__slots__ = 'commands'

	def __init__(self):
		self.commands = []

	def add(self, cmd):
		if self.len() == 4:
			return ( False )
		else :
			self.commands.append(cmd)
			return ( True )

	def terminate(self):
		if (self.len() < 4):
			for i in range(self.len(),4):
				self.commands.append(_nds_cmdpack_nop())

	def len(self):
		return ( len(self.commands) )

	def get_nb_param(self):
		if self.len() == 0:
			return ( 0 )
		else :
			nb = 1

		for i in self.commands:
			nb += i.get_nb_val()

		return ( nb )

	def get_pack(self,format):
		if ( format == 'TEXT' ) :
			str = ""
		else :
			str = b""
		str += self.get_cmd(format)
		str += self.get_val(format)
		return ( str )

	def get_cmd(self,format):
		c = self.commands
		if ( format == 'TEXT' ) :
			cmd = ""
			cmd += "FIFO_COMMAND_PACK( %s , %s , %s , %s ),\n" % ( c[0].get_cmd(format) ,c[1].get_cmd(format) ,c[2].get_cmd(format) ,c[3].get_cmd(format) )
		elif ( format == 'BINARY' ) :
			#cmd = b""
			cmd = c[0].get_cmd(format) + c[1].get_cmd(format) + c[2].get_cmd(format) + c[3].get_cmd(format)
			#cmd = struct.pack('ssss' , c[0].get_cmd(format) , c[1].get_cmd(format) , c[2].get_cmd(format) , c[3].get_cmd(format) )
		return cmd

	def get_val(self,format):
		if ( format == 'TEXT' ) :
			val = ""
			for i in self.commands:
				if ( i.get_val(format) != None ):
					val += i.get_val(format)
					val += ",\n"
		else:
			val = b""
			for i in self.commands:
				if ( i.get_val(format) != None ):
					val += i.get_val(format)

		return val

	def __str__(self):
		str = "CMD_PACK ELEMENT:\n"
		for i in self.commands:
			str += "%s\n" % (i)
		return ( str )



class _nds_cmdpack_list (object):
	__slots__ = 'list'

	def __init__(self):
		self.list = [ _nds_cmdpack() ]

	def add(self,cmd):
		if ( self.list[-1].add(cmd) == False ):
			self.list.append( _nds_cmdpack() )
			self.list[-1].add(cmd)

	def len(self):
		return ( len(self.list) )

	def get_nb_params(self):
		nb = 0
		for i in self.list :
			nb += i.get_nb_param()

		return ( nb )

	def terminate(self):
		self.list[-1].terminate()

	def get_pack(self,format):
		if (format == 'TEXT') :
			packs = ""
		else :
			packs = b""

		for cp in self.list:
			#print("CP :", cp)
			#print("TYPE:",type(cp.get_pack(format)))
			#print("LENGTH:",len(cp.get_pack(format)))
			
			packs += cp.get_pack(format)
				
		return ( packs )

	def __str__(self):
		str = "COMMAND_PACK LIST\n"
		for i in self.list :
			str += "%s" % ( i )
		return ( str )


class _nds_mesh (object) :
	__slots__ = 'name', 'quads' , 'triangles' , 'texture' , 'cmdpack_list' , 'cmdpack_count' , 'options', 'final_cmdpack'


	def __init__(self,mesh_options):
		print( mesh_options )
		self.options = mesh_options
		self.quads = []
		self.triangles = []
		self.cmdpack_list = _nds_cmdpack_list()
#		print( self.cmdpack_list )
		self.cmdpack_count = 0
		

		self.name = mesh_options.mesh_name
		self.get_faces(mesh_options.mesh_data)
		#self.rescale_mesh(mesh_options.mesh_data)

		self.prepare_cmdpack()
#		print( self.cmdpack_list)
		self.construct_cmdpack()

	def save_tex(self) :
		try:
			import PIL.Image
		except ImportError :
			print( "Python Imaging Library not installed" )
		else :
			print( self.options.texture_data[0].filename )
#			print( Blender.sys.expandpath(self.options.texture_data[0].filename) )
			if (self.options.texture_data[0].packed ) : self.options.texture_data[0].unpack(Blender.UnpackModes.USE_LOCAL)
			img = PIL.Image.open(Blender.sys.expandpath(self.options.texture_data[0].getFilename()))
			img_rgb = img.convert("RGB")
			img_pal = img_rgb.convert("P",palette=PIL.Image.ADAPTIVE)
			img_res = img_pal.resize((self.options.texture_w,self.options.texture_h) )
			img_res.save(self.options.get_final_path_tex())


	def add_nds_mesh_vertex(self,blender_mesh , face,face_list):
		for n,i in enumerate(face.verts):
			nds_mesh_vertex = _nds_mesh_vertex()
			#we copy vertex's coordinates information
			nds_mesh_vertex.vertex = _nds_cmdpack_vertex(blender_mesh.verts[i].co)
			#we copy vertex's normals information
			if (self.options.normals_export):
				nds_mesh_vertex.normal = _nds_cmdpack_normal(blender_mesh.verts[i].normal)
			#we copy vertex's UV coordinates information only if there is UV layer for the current mesh
			if (self.options.uv_export) :
				uv = blender_mesh.active_uv_texture.data[face.index].uv[n]
				
#				for n,ut in enumerate(blender_mesh.active_uv_texture.data) :
#					for u in ut.uv : print(n,float(u[0]), float(u[1]))
#				if (face.uv[i].x >= 0 and face.uv[i].y >= 0):
				nds_mesh_vertex.uv = _nds_cmdpack_texture( ( uv[0] * self.options.texture_w , (1-uv[1]) * self.options.texture_h))
				#nds_mesh_vertex.uv = _nds_cmdpack_texture( ( uv[0] , (1-uv[1])))
			#we copy vertex's color only if there is Color Layer for the current mesh
			if (self.options.color_export) :
				nds_mesh_vertex.color = _nds_cmdpack_color( (face.col[i].r * 32 / 256 , face.col[i].g * 32 / 256, face.col[i].b * 32 / 256) )
			#finally, we append the nds_mesh_vertex in the quads list
			face_list.append(nds_mesh_vertex)

	def get_faces(self,blender_mesh):
		for face in blender_mesh.faces :
			#we process the face only if this is a quad
			if (len(face.verts) == 4) :
				self.add_nds_mesh_vertex(blender_mesh , face , self.quads)
			#we process the face only if this is a triangle
			elif (len(face.verts) == 3) :
				self.add_nds_mesh_vertex(blender_mesh , face , self.triangles)

	"""TODO : I think there is a need to rescale the mesh because the range in the NDS is [-8.0, 8.0[ but I need to do some tests before"""
	def rescale_mesh(self,blender_mesh):
		max_x=max_y=max_z=min_x=min_y=min_z=max_l=0
		for v in blender_mesh.verts:
			if v.co[0]>max_x : max_x = v.co[0]
			elif v.co[0]<min_x : min_x = v.co[0]
			if v.co[1]>max_y : max_y = v.co[1]
			elif v.co[1]<min_y : min_y = v.co[1]
			if v.co[2]>max_z : max_z = v.co[2]
			elif v.co[2]<min_z : min_z = v.co[2]
		if (abs(max_x-min_x) > max_l) : max_l = abs(max_x-min_x)
		if (abs(max_y-min_y) > max_l) : max_l = abs(max_y-min_y)
		if (abs(max_z-min_z) > max_l) : max_l = abs(max_z-min_z)

		if (len(self.quads)>0):
			for f in self.quads:
				v=f.vertex
				f.vertex.x = v.x/max_l
				f.vertex.y = v.y/max_l
				f.vertex.z = v.z/max_l
		if (len(self.triangles)>0):
			for f in self.triangles:
				v=f.vertex
				f.vertex.x = v.x/max_l
				f.vertex.y = v.y/max_l
				f.vertex.z = v.z/max_l
		print( "longueur max = %s" % (max_l) )

	def prepare_cmdpack(self):
		#If there is at least 1 quad
		if ( len(self.quads) > 0 ) :
			#Begin Quads list
			self.cmdpack_list.add( _nds_cmdpack_begin('GL_QUADS') )

			for i in range( len(self.quads) ) :

				v = self.quads[i]

				if ( self.options.color_export and v.color != None ) :
					self.cmdpack_list.add(v.color)

				if (self.options.uv_export and v.uv != None) :
					self.cmdpack_list.add(v.uv)

				if (self.options.normals_export and v.normal != None):
					self.cmdpack_list.add(v.normal)

				if (v.vertex != None) :
					self.cmdpack_list.add(v.vertex)
			#End Quads list
			self.cmdpack_list.add( _nds_cmdpack_end() )

		#If there is at least 1 triangle
		if ( len(self.triangles) > 0 ) :
			#Begin Triangles list
			self.cmdpack_list.add( _nds_cmdpack_begin('GL_TRIANGLES') )

			for i in range( len(self.triangles) ) :

				v = self.triangles[i]

				if ( self.options.color_export and v.color != None ) :
					self.cmdpack_list.add(v.color)

				if (self.options.uv_export and v.uv != None) :
					self.cmdpack_list.add(v.uv)

				if (self.options.normals_export and v.normal != None):
					self.cmdpack_list.add(v.normal)

				if (v.vertex != None) :
					self.cmdpack_list.add(v.vertex)
			#End Quads list
			self.cmdpack_list.add( _nds_cmdpack_end() )

		#Fill the remaining cmd slots with NOP commands
		self.cmdpack_list.terminate()

	def construct_cmdpack(self):

		if (self.options.format == 'TEXT') :
			self.final_cmdpack = ""
			s = "const unsigned long %s[] = {\n%d,\n%s" % ( self.options.mesh_name , self.cmdpack_list.get_nb_params() , self.cmdpack_list.get_pack(self.options.format) )
			self.final_cmdpack += s[0:-2]
			self.final_cmdpack += "\n};\n"
		elif (self.options.format == 'BINARY') :
			self.final_cmdpack = b"";
			self.final_cmdpack += struct.pack( '<i' , self.cmdpack_list.get_nb_params())
			self.final_cmdpack += self.cmdpack_list.get_pack(self.options.format)
			


	def save(self) :
		
		print( 'saving %s in path %s' % (self,self.options.get_final_path_mesh()))

		if(self.options.format == 'TEXT') :
			f = open(self.options.get_final_path_mesh()+".c","w")
			f.write("#include \"%s\"\n"%(self.options.mesh_name+".h")+ self.final_cmdpack)
			f.close();
			f = open(self.options.get_final_path_mesh()+".h","w")
			f.write(
"""#ifndef _DATA_%s
#define _DATA_%s
#include <nds.h>
extern const unsigned long %s[];
#endif
""" % (self.options.mesh_name, self.options.mesh_name , self.options.mesh_name) )
			f.close();
		elif (self.options.format == 'BINARY'):
			f = open(self.options.get_final_path_mesh()+".bin","wb")
			f.write(self.final_cmdpack)
			f.close();

		if (self.options.texfile_export) : self.save_tex()

	def __str__(self):
		return "NDS Mesh [%s], Faces = %d (Quads=%d, Triangles=%d), Texture=%s" % (self.name,len(self.quads)/4+len(self.triangles)/3,len(self.quads)/4,len(self.triangles)/3,repr((self.options.get_final_path_tex(), self.options.texture_w,self.options.texture_h)) )


class _menu_nds_export (object) :
	__slots__ = 'nb_meshes', 'mesh_options','selected_menu_mesh','popup_elm','button' , 'texID' , 'nds_export'

	def __init__(self,properties, context):
		print ( dir(properties.meshes) )
		if (len(properties.meshes) == 0):
			self.nds_list_meshes(context)

	def nds_list_meshes(self , context) :
		print( "List Meshes in data" )

		if ( len(self.properties.meshes) == 0) :
			meshes = None
			if hasattr(context,'selected_objects'):
				meshes = context.selected_objects


		self.nb_meshes = 0
		self.mesh_options = []
		if meshes:
			for mesh in meshes :
				if (type(mesh.data)==bpy.types.Mesh) :
					self.mesh_options.append( _mesh_options( mesh.data , dir_path) )
					self.nb_meshes += 1

		button = []

		if(self.nb_meshes > 0) :
			self.nds_export = _nds_mesh(self.mesh_options[0])

class MeshNDS(bpy.types.IDPropertyGroup):
    pass

class ExportNDS(bpy.types.Operator) :
	'''Export to Nintendo DS Binary CallList'''
	bl_idname = "export.nds_calllist"
	bl_label = "Export NintendoDS CallList"

	path = bpy.props.StringProperty(name='Path' , description="Path used for exporting Nintendo DS Binary CallList" , maxlen=1024 , default="")
	filename = bpy.props.StringProperty(name='FileName' , description="FileName used for exporting Nintendo DS Binary CallList" , maxlen=1024 , default="")
	directory = bpy.props.StringProperty(name='Directory' , description="Directory used for exporting Nintendo DS Binary CallList" , maxlen=1024 , default="")

	export_uvs = bpy.props.BoolProperty(name='Export UV' , description="Flag for exporting UV coordinates" , default=DEFAULT_OPTIONS['UV']);
	export_colors = bpy.props.BoolProperty(name='Export Color' , description="Flag for exporting Colors" , default=DEFAULT_OPTIONS['COLOR']);
	export_normals = bpy.props.BoolProperty(name='Export Normals' , description="Flag for exporting Normals" , default=DEFAULT_OPTIONS['NORMAL']);
	file_format = bpy.props.StringProperty(name='File Format' , description="File Format to export" , maxlen=1024 , default=DEFAULT_OPTIONS['FORMAT'])
	export_armature = bpy.props.BoolProperty(name='Export Armature', description="Flag for exporting Armature animation" , default=DEFAULT_OPTIONS['ARMATURE'])

	meshes = bpy.props.StringProperty(name='Mesh(es) Name' , description="List of Mesh(es) Name to export separated by comma" , maxlen=1024, default="all")

	def execute(self , context) :
		print("Path:%s" % self.properties.path)
		print("Filename:%s" % self.properties.filename)
		print("Directory:%s" % self.properties.directory)
		print("Options: export_uvs=%s export_colors=%s export_normals=%s file_format=%s" % (self.export_uvs , self.export_colors, self.export_normals, self.file_format))
		print("mesh_name",self.meshes)
		
		objects = []
		meshes = []
		meshes_to_clean = []

		#print(dir(context.main))

		if ( hasattr(context , 'selected_objects') ):
			print ('%d Selected Objects detected' % (len(context.selected_objects) ) )
			for obj in context.selected_objects :
				print ('%s [%s]' % (obj.data, type(obj.data)) )
				if ( type(obj.data) == bpy.types.Mesh ) :
					objects.append(obj)
		else : #Export all exportable meshes (means we are in background mode)
			for obj in bpy.data.objects:
				if ( type(obj.data) == bpy.types.Mesh ) :
					objects.append(obj)

		for obj in objects:
			anim_data = obj.animation_data
			if (anim_data != None ) : 
				print("object %s has Animation Data ..." % obj.name)
				print("%s %s" % (anim_data, type(anim_data)) )
				scn = context.scene
				frames = range(scn.start_frame , scn.end_frame + 1)
				name_fmt = "%%0%dd" % (len("%s" % len(frames)))
				for i in frames:
					scn.set_frame(i)
					mesh = obj.create_mesh(True,'RENDER')
					mesh.name = ("%s_%s_" + name_fmt) % (obj.data.name ,anim_data.action.name, int(i))
					meshes.append(mesh)
					meshes_to_clean.append(mesh)
			else:
				print("object %s has no Armature(s) = armature export disabled")
				self.export_armature = False
				meshes.append(obj.data)

		for mesh in meshes:
			print('building export of mesh %s' % mesh.name)
			nds_mesh = _nds_mesh( _mesh_options( mesh , self.properties.directory, self.export_uvs , self.export_colors, self.export_normals , self.export_armature, self.file_format) )
			nds_mesh.save()
			
		for mesh in meshes_to_clean :
			context.main.meshes.remove(mesh)

		return {'FINISHED'}

	def invoke(self, context, event) :
		wm = context.manager
		wm.add_fileselect(self)
		return {'RUNNING_MODAL'}

#	def poll(self, context):
#		print("NDS Poll")
#		return True

	
bpy.types.register(ExportNDS)

def menu_func(self, context):
	default_path = bpy.data.filename.replace(".blend", ".bin")
	self.layout.operator(ExportNDS.bl_idname, text="NintendoDS CallList").path = default_path

#menu_item = dynamic_menu.add(bpy.types.INFO_MT_file_export, menu_func)
bpy.types.INFO_MT_file_export.append(menu_func)

	
	
#def my_callback(filename):
#	if filename.find('/', -2) <= 0: filename += '.h' # add '.h' if the user didn't
#	#print Blender.sys.dirname(filename)
#	DSexport(Blender.sys.dirname(filename))
#
#
#fname = Blender.sys.makename(ext = "")
#Blender.Window.FileSelector(my_callback, "Select a directory","")
