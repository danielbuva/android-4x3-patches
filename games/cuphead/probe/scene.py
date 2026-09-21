"""Selective decorative-camera layer, tied to the investigated scene revision."""
import hashlib
import UnityPy
from android4x3.errors import PatchError

SCENE = 'assets/bin/Data/level41'
SOURCE = '045d05b685a86d1b0da432f62cae90ad6f15acd334e99c55f3513031026772e1'
PATCHED = '4e66983df08665b69ac40a2b784c3c341f42a1f5b188c2f89493d06b601cef03'


def patch_scene(data):
    checksum = hashlib.sha256(data).hexdigest()
    if checksum == PATCHED:
        return data
    if checksum != SOURCE:
        raise PatchError('Unsupported Forest Follies scene; no changes made')
    environment = UnityPy.load(data)
    objects = {o.path_id: o for o in environment.objects}
    selected = set()
    for obj in objects.values():
        if obj.type.name != 'GameObject':
            continue
        tree = obj.read_typetree()
        if tree['m_Layer'] == 29:
            raise PatchError('Decorative camera layer is already occupied')
        name = tree['m_Name']
        if not (name.startswith(('lv1-1_bg_', 'lv1-1_bgfar_', 'lv1-1_farbg_'))
                or name == 'lv1-1_mg_meadow-loop'):
            continue
        components = [objects[c['component']['m_PathID']] for c in tree['m_Component']]
        if any(c.type.name not in ('Transform', 'SpriteRenderer', 'MonoBehaviour') for c in components):
            continue
        transforms = [c.read_typetree() for c in components if c.type.name == 'Transform']
        renderers = [c.read_typetree() for c in components if c.type.name == 'SpriteRenderer']
        if (len(transforms) != 1 or transforms[0]['m_Children'] or len(renderers) != 1
                or renderers[0]['m_SortingLayerID'] != 1476054201):
            continue
        scripts = [c.read_typetree(check_read=False)['m_Script']
                   for c in components if c.type.name == 'MonoBehaviour']
        # PlatformingLevelParallax in this hash-guarded scene; exclude ScrollingSprite.
        if any(s != {'m_FileID': 1, 'm_PathID': 793} for s in scripts):
            continue
        if tree['m_Layer'] != 0:
            raise PatchError('Unexpected decorative object layer')
        tree['m_Layer'] = 29
        obj.save_typetree(tree)
        selected.add(obj.path_id)
    if len(selected) != 48:
        raise PatchError('Expected exactly 48 decorative leaf objects')
    output = environment.file.save()
    if hashlib.sha256(output).hexdigest() != PATCHED:
        raise PatchError('Unexpected modified scene checksum')
    # No transforms, sprites, collision shapes or other component data may change.
    after = {o.path_id: o for o in UnityPy.load(output).objects}
    for obj in UnityPy.load(data).objects:
        other = after[obj.path_id]
        if obj.path_id not in selected:
            if obj.get_raw_data() != other.get_raw_data():
                raise PatchError('Unrelated scene object changed')
        else:
            before_tree, after_tree = obj.read_typetree(), other.read_typetree()
            after_tree['m_Layer'] = before_tree['m_Layer']
            if before_tree != after_tree:
                raise PatchError('Decorative object changed beyond its render layer')
    return output
