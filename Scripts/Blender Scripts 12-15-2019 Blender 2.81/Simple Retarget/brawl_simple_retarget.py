'''
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

'''
Auto orient, point, and scale, constrain two skeletal joint hierarchies
according to names. Offsets maintained.

Requirements:
    -if you use (matchScale=True), then only uniform scaling will work. 
        By uniform I mean that ScaleX = ScaleY = ScaleZ, always.
    -if you use (matchTranslation=True) and (matchRotation=True),
        then you MUST overlay the Brawl model over the Sm4sh model.
        Each match-bone MUST overlay a top eachother near perfectly.
        
Procedure:
    Select Owner (Brawl) any joint (selection order doesnt matter)
    Select Source (Sm4sh) any joint (selection order doesnt matter)
    Search Op: (View3D) 'Brawl Simple Retarget Constraints' 
    That will setup all the necessary constraints for the retargeting. Now you just have to set the animation on the sm4sh/ult armature and bake (below).

    Then select the Sm4sh/Ult armature and set the desired animation. 
    Then select the Brawl armature and bake to the brawl bones, keeping the constraints if you're going to retarget other animations, clearing otherwise.
    If you keep the constraints, then the animation will appear wrong but it's actually OK. Once the constraints are removed, the animation will be fine.
    
'''
import math
import os
import re
from math import atan2, ceil, cos, degrees, floor, isclose, pi, radians, sin,tan

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty,CollectionProperty
from mathutils import Euler, Matrix, Quaternion, Vector

from bpy.types import  AddonPreferences
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       CollectionProperty,
                       FloatVectorProperty
                       )
                       
bl_info = {
    "name": "Brawl Simple Retarget",
    "author": "Wayde Brandon Moss",
    "version": (1, 0),
    "blender": (2, 81, 0),
    "location": "View3D, Search: 'Brawl Simple Retarget Constraints'",
    "description": "Constrains a brawl armature to an Sm4sh/Ultimate armature for retargeting",
    "category": "Animation",
    }

brawl_to_ult_name_remap = {
'TransN' : 'Trans',
'XRotN' : 'Rot',
'HipN' : 'Hip',
'LLegJ' : 'LegL',
'LKneeJ' : 'KneeL',
'LFootJ' : 'FootL',
'LToeN' : 'ToeL',
'RLegJ' : 'LegR',
'RKneeJ' : 'KneeR',
'RFootJ' : 'FootR',
'RToeN' : 'ToeR',
'WaistN' : 'Waist',
'BustN' : 'Bust',
'LShoulderN' : 'ClavicleL',
'LShoulderJ' : 'ShoulderL',
'LArmJ' : 'ArmL',
'LHandN' : 'HandL',
'L1stNa' : 'FingerL11',
'L1stNb' : 'FingerL12',
'L2ndNa' : 'FingerL21',
'L2ndNb' : 'FingerL22',
'L3rdNa' : 'FingerL31',
'L3rdNb' : 'FingerL32',
'L4thNa' : 'FingerL41',
'L4thNb' : 'FingerL42',
'LThumbNa' : 'FingerL51',
'LThumbNb' : 'FingerL52',
'LHaveN' : 'HaveL',
'RShoulderN' : 'ClavicleR',
'RShoulderJ' : 'ShoulderR',
'RArmJ' : 'ArmR',
'RHandN' : 'HandR',
'R1stNa' : 'FingerR11',
'R1stNb' : 'FingerR12',
'R2ndNa' : 'FingerR21',
'R2ndNb' : 'FingerR22',
'R3rdNa' : 'FingerR31',
'R3rdNb' : 'FingerR32',
'R4thNa' : 'FingerR41',
'R4thNb' : 'FingerR42',
'RThumbNa' : 'FingerR51',
'RThumbNb' : 'FingerR52',
'RHaveN' : 'HaveR',
'NeckN' : 'Neck',
'HeadN' : 'Head',
'MouthN' : 'Jaw',
'JawJ' : 'Jaw',
'ThrowN' : 'Throw',
}
__bl_classes = []
def register_wrap(cls):
    if hasattr(cls, 'bl_rna'):
        __bl_classes.append(cls)
    return cls

@register_wrap
class RemapItem(PropertyGroup):
    brawl_bone : StringProperty()
    ult_bone : StringProperty()

@register_wrap
class RetargetPreferences(AddonPreferences):
    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__

    remap : CollectionProperty(type=RemapItem)
    
    def draw(self, context):
        layout = self.layout
        
        row = layout.row(align=True)
        row.operator(Preferences_Add_Item.bl_idname,text='',icon='ADD')
        row.label(text='Remap (Brawl - Ult)')
        row.operator(Preferences_Reset_Item.bl_idname,text='Reset to Default',icon='FILE_REFRESH')

        col = layout.column(align=True)
        length = len(self.remap)
        for i,item in enumerate(reversed(self.remap)):
            row = col.row(align=True)
            row.operator(Preferences_Remove_Item.bl_idname,text='',icon='REMOVE').item_index = length - 1 - i 
            row.prop(item,'brawl_bone',text='')
            row.prop(item,'ult_bone',text='')


def simple_retarget(context,matches,target,owner_object,match_translation,match_rotation,match_scale):

        context.view_layer.objects.active = owner_object
        bpy.ops.object.mode_set(mode='EDIT')
        if 'redirect_root' not in owner_object.data.edit_bones:
            redirect_root = owner_object.data.edit_bones.new('redirect_root')
            redirect_root.tail = Vector((0,1,0))
        redirect_root = owner_object.data.edit_bones['redirect_root']

        for owner_name,subtarget_name in matches.items():
            owner = owner_object.data.bones[owner_name]

            if 'redirect_' + owner_name not in owner_object.data.edit_bones:
                edit_bone = owner_object.data.edit_bones.new('redirect_' + owner_name)
                
            edit_bone = owner_object.data.edit_bones['redirect_' + owner_name]
            edit_bone.head = Vector((0,0,0))
            edit_bone.tail = edit_bone.head + Vector((0,1,0))
            edit_bone.roll=0

            if 'brawl_bind' in owner:
                edit_bone.matrix =  matrix_from_sequence(owner['brawl_bind'])
            else:
                edit_bone.matrix = owner.matrix 

            #parenting for easy deletion later by user
            edit_bone.parent = redirect_root


        #return {'FINISHED'}
        bpy.ops.object.mode_set(mode='POSE')
        for owner_name,subtarget_name in matches.items():
            
            owner = owner_object.pose.bones[owner_name]
            owner_redirect = owner_object.pose.bones['redirect_' + owner_name]
            subtarget = target.pose.bones[subtarget_name]

            con = owner_redirect.constraints.new('CHILD_OF')
            con.inverse_matrix = (subtarget.bone.matrix_local).inverted()  
            con.target = target
            con.subtarget= subtarget_name 
            con.use_location_x = True
            con.use_location_y = True
            con.use_location_z = True

            con.use_rotation_x = True
            con.use_rotation_y = True
            con.use_rotation_z = True

            con.use_scale_x = True
            con.use_scale_y = True
            con.use_scale_z = True

                
            #needed for bpy.ops.constraint.childof_set_inverse
            #owner.bone.select = True 
            #owner_object.data.bones.active = owner.bone 
            if match_translation:
                con = owner.constraints.new('COPY_LOCATION')
                con.target = owner_object
                con.subtarget= owner_redirect.name 
                con.owner_space = 'WORLD'
                con.target_space = 'WORLD'
                con.invert_x= False 
                con.invert_y= False 
                con.invert_z= False 
                con.use_x = True
                con.use_y = True
                con.use_z = True
                con.use_offset =  False 
                con.mute=False

            if match_rotation  :
                con = owner.constraints.new('COPY_ROTATION')
                con.target = owner_object
                con.subtarget= owner_redirect.name 
                con.owner_space = 'WORLD'
                con.target_space = 'WORLD'
                con.invert_x= False 
                con.invert_y= False 
                con.invert_z= False 
                con.use_x = True
                con.use_y = True
                con.use_z = True
                con.use_offset =  False 
                con.mute=False
                
            if match_scale :
                con = owner.constraints.new('COPY_SCALE')
                con.target = owner_object
                con.subtarget= owner_redirect.name 
                con.owner_space = 'WORLD'
                con.target_space = 'WORLD'
                con.use_x = True
                con.use_y = True
                con.use_z = True
                con.use_offset =  False 
                con.mute=False

        print()
def matrix_from_sequence(sequence):
    return Matrix((sequence[0:4],sequence[4:8],sequence[8:12],sequence[12:16]))
@register_wrap
class POSE_Brawl_Simple_Retarget_Constrain(bpy.types.Operator):
    '''
    Requires 2 selected armatures, the brawl and non-brawl model.
    '''
    bl_idname = "brawlbox.simple_retarget_constrain"
    bl_label = "Brawl Simple Retarget Constraints"
    bl_options = {'REGISTER', 'UNDO'}
    bl_context = "posemode"

    match_translation : BoolProperty(name='Match Translation',default=True)
    match_rotation : BoolProperty(name='Match Rotation',default=True)
    match_scale : BoolProperty(name='Match Scale',default=True)

    @classmethod
    def poll(cls,context):
        return  (len(context.selected_objects) == 2) and (isinstance(context.selected_objects[0].data,bpy.types.Armature) and isinstance(context.selected_objects[1].data,bpy.types.Armature))

    def execute(self,context):
        '''
        Assumes both armatures set to identity

        (dummy)Duplicate owners to a bone without any parents.
        make dummy child of target
        make original owner copy xform from dummy.

        This setup removes parent influence over owner for childof constraints.
        '''
        
        bpy.ops.object.mode_set(mode='POSE')

        owner_object = [obj for obj in context.selected_objects if 'brawl_root' in obj][0]
        owner_bones = owner_object.pose.bones 
        target = [obj for obj in context.selected_objects if obj != owner_object][0]
        target_bones = target.pose.bones

        no_match = []
        matches = {}
        
        brawl_to_ult_name_remap = {} 
        prefs = bpy.context.preferences.addons[RetargetPreferences.bl_idname].preferences 
        for item in prefs.remap:
            brawl_to_ult_name_remap[item.brawl_bone] = item.ult_bone

        print('matches: ')
        for owner in owner_bones:
            ult_bone_name = None 
            if owner.name in target_bones:
                ult_bone_name = owner.name
            elif owner.name in brawl_to_ult_name_remap:
                ult_bone_name = brawl_to_ult_name_remap[owner.name]

            if ult_bone_name is not None:
                print('Match found: brawl:{0} | ult:{1}'.format(owner.name,ult_bone_name))
                matches[owner.name] = ult_bone_name
            else:
                no_match.append(owner.name)
        
        simple_retarget(context,matches,target,owner_object,self.match_translation,self.match_rotation,self.match_scale)

        print('no matches:')
        for owner_name in no_match:
            print("No match for brawl:{0}".format(owner_name))
        print() 

        #show so its more obvious script worked
        context.view_layer.objects.active = owner_object
        return {'FINISHED'}

@register_wrap
class Preferences_Add_Item(bpy.types.Operator):
    bl_idname = "brawlbox.add_retarget_item"
    bl_label = "Brawl Add Retarget Item"
    bl_options = {'REGISTER', 'UNDO','INTERNAL'}
    bl_context = "posemode"

    def execute(self,context):
        
        prefs = bpy.context.preferences.addons[RetargetPreferences.bl_idname].preferences 
        item = prefs.remap.add()

        return {'FINISHED'}

@register_wrap
class Preferences_Remove_Item(bpy.types.Operator):
    bl_idname = "brawlbox.remove_retarget_item"
    bl_label = "Brawl Remove Retarget Item"
    bl_options = {'REGISTER', 'UNDO','INTERNAL'}
    bl_context = "posemode"

    item_index : IntProperty()
    def execute(self,context):
        
        prefs = bpy.context.preferences.addons[RetargetPreferences.bl_idname].preferences 
        prefs.remap.remove(self.item_index)

        return {'FINISHED'}

@register_wrap
class Preferences_Reset_Item(bpy.types.Operator):
    bl_idname = "brawlbox.reset_retarget_map"
    bl_label = "Brawl Reset Retarget Map"
    bl_options = {'REGISTER', 'UNDO','INTERNAL'}
    bl_context = "posemode"

    item_index : IntProperty()
    def execute(self,context):
        
        prefs = bpy.context.preferences.addons[RetargetPreferences.bl_idname].preferences 
        prefs.remap.clear()
        if len(prefs.remap) == 0: 
            for brawl,ult in brawl_to_ult_name_remap.items():
                item = prefs.remap.add()
                item.brawl_bone = brawl 
                item.ult_bone = ult 


        return {'FINISHED'}
def matrix_trs(translation, quaternion, scale):
    return Matrix.Translation(translation) @ quaternion.to_matrix().to_4x4() @ Matrix.Scale(scale[0],4,(1,0,0)) @ Matrix.Scale(scale[1],4,(0,1,0)) @ Matrix.Scale(scale[2],4,(0,0,1))
def register():
    from bpy.utils import register_class
    for cls in __bl_classes:
        register_class(cls)
            
    prefs = bpy.context.preferences.addons[RetargetPreferences.bl_idname].preferences 
    if len(prefs.remap) == 0: 
        for brawl,ult in brawl_to_ult_name_remap.items():
            item = prefs.remap.add()
            item.brawl_bone = brawl 
            item.ult_bone = ult 


def unregister():
    from bpy.utils import unregister_class
    for cls in __bl_classes:
        unregister_class(cls)


if __name__ == "__main__":
    register()

