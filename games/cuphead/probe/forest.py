"""Optional, narrowly scoped Forest Follies decorative meadow trial."""
import copy
import hashlib
from android4x3.errors import PatchError

ENTRY = 'assets/bin/Data/level41'
SOURCE = '045d05b685a86d1b0da432f62cae90ad6f15acd334e99c55f3513031026772e1'
PATCHED = '4599b46096eb8dc29b3e3191e324fa0a87c750bb8408187e59f52052a562c336'
NAME = 'lv1-1_mg_meadow-loop'


def fit_transform(tree):
    result = copy.deepcopy(tree)
    if tree['m_Children'] or tree['m_LocalScale'] != {'x':1.0,'y':1.0,'z':1.0}:
        raise PatchError('Unexpected decorative meadow transform')
    if tree['m_LocalPosition'] != {'x':624.0,'y':-110.0,'z':0.0}:
        raise PatchError('Unexpected decorative meadow position')
    halfheight = (137 / 0.40217500925064087) / 2
    result['m_LocalPosition']['y'] -= halfheight * 0.5
    result['m_LocalScale']['x'] = 1.5
    result['m_LocalScale']['y'] = 1.5
    return result


def patch(data):
    checksum = hashlib.sha256(data).hexdigest()
    if checksum == PATCHED:
        return data
    if checksum != SOURCE:
        raise PatchError('Unsupported Forest Follies scene; no artwork changes made')
    import UnityPy
    environment = UnityPy.load(data)
    objects = {o.path_id:o for o in environment.objects}
    targets = [o.read_typetree() for o in objects.values()
               if o.type.name == 'GameObject' and o.read_typetree().get('m_Name') == NAME]
    if len(targets) != 1:
        raise PatchError('Decorative meadow target is not unique')
    components = [objects[c['component']['m_PathID']] for c in targets[0]['m_Component']]
    if sorted(o.type.name for o in components) != ['SpriteRenderer','Transform']:
        raise PatchError('Meadow target contains unexpected components')
    transform = next(o for o in components if o.type.name == 'Transform')
    transform.save_typetree(fit_transform(transform.read_typetree()))
    output = environment.file.save()
    if hashlib.sha256(output).hexdigest() != PATCHED:
        raise PatchError('Unexpected serialized artwork result; check pinned UnityPy version')
    return output
