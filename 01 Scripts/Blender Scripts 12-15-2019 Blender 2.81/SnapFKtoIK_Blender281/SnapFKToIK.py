'''
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''
bl_info = {
    "name": "Snap FK to IK",
    "author": "Wayde Brandon Moss",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "(Pose Mode)operator: Snap FK to IK",
    "description": "For the selected bones, snap from FK to IK/CopyRotation subtarget.",
    "category": "Animation",
    }
import bpy
from math import cos, sin
from mathutils import Matrix, Vector 


def matrix_trs(translation,quaternion,scale):
    return Matrix.Translation(translation) @ quaternion.to_matrix().to_4x4() @ Matrix.Scale(scale[0],4,(1,0,0)) @ Matrix.Scale(scale[1],4,(0,1,0)) @ Matrix.Scale(scale[2],4,(0,0,1))
def snap_fk_to_ik(con,owner):
    chain = []
    chain_count = con.chain_count
    cur = owner

    if chain_count != 0:
        i = 1
        while cur.parent is not None and i < chain_count:
            cur = cur.parent
            chain.append(cur)
            i+=1
    else:
        while cur.parent is not None:
            cur = cur.parent
            chain.append(cur)
        

    pose_base_bone = chain[-1]
    
    bones = con.target.pose.bones
    ik_subtarget  = bones[con.subtarget]
    
    targ_loc,targ_rot,targ_scale = ik_subtarget.matrix.decompose()
    #put target at owner tail location in armature space
    targ_loc =  (Matrix.Translation(owner.vector) @ owner.matrix).to_translation()
    ik_subtarget.matrix= matrix_trs(targ_loc,targ_rot,targ_scale)
    ik_subtarget.keyframe_insert(data_path='location',group=ik_subtarget.name)

    if con.pole_subtarget:
        ik_pole = bones[con.pole_subtarget]
        pole_loc,pole_rot,pole_scale = ik_pole.matrix.decompose()

        #pole coords are relative to base bone
        pole_angle = con.pole_angle
        pole_x = cos(pole_angle)
        pole_z = sin(pole_angle)
        pole_axis = Vector((pole_x, 0, pole_z))
        pole_offset = pole_axis * pose_base_bone.vector.length * 2

        #xform pole coords from base_bone space to armature space
        pole_loc  = pose_base_bone.matrix @ pole_offset

        ik_pole.matrix= matrix_trs(pole_loc,pole_rot,pole_scale)
            
        ik_pole.keyframe_insert(data_path='location',group=ik_pole.name)
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    #con.mute = Falsea
def snap_fk_to_ik_rotation(con,owner):
    target = con.target 
    subtarget = target.pose.bones[con.subtarget]

    _,owner_rot,_ = owner.matrix.decompose() 
    subtarget_loc,_,subtarget_scale = subtarget.matrix.decompose()

    subtarget.matrix = matrix_trs(subtarget_loc,owner_rot,subtarget_scale)

    if subtarget.rotation_mode == 'QUATERNION':
        subtarget.keyframe_insert(data_path='rotation_quaternion',group = subtarget.name)
    elif subtarget.rotation_mode == 'AXIS_ANGLE':
        subtarget.keyframe_insert(data_path='rotation_axis_angle',group = subtarget.name)
    else:
        subtarget.keyframe_insert(data_path='rotation_euler',group = subtarget.name)
    
    
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
class POSE_OT_IK_SNAP(bpy.types.Operator):
    bl_idname = "pose.snap_fk_to_ik"
    bl_label = "Snap FK to IK"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print()
        for owner in bpy.context.selected_pose_bones:
            for con in owner.constraints:
                if isinstance(con,bpy.types.KinematicConstraint):
                    print('snapped FK to IK: Owner:{0} IK_Subtarget:{1}'.format(owner.name,con.subtarget))
                    snap_fk_to_ik(con,owner)
                elif isinstance(con,bpy.types.CopyRotationConstraint):
                    print('snapped FK to IK (rotation): Owner:{0} IK_Subtarget:{1}'.format(owner.name,con.subtarget))
                    snap_fk_to_ik_rotation(con,owner)
                    
        return {'FINISHED'}
classes =  (POSE_OT_IK_SNAP,
)
def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)



if __name__ == "__main__":
    register()