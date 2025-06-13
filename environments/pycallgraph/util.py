class Util(object):

    @staticmethod
    def human_readable_bibyte(num):
        num = float(num)
        for x in ['B', 'KiB', 'MiB', 'GiB']:
            if num < 1024 and num > -1024:
                return '{:3.1f}{}'.format(num, x)
            num /= 1024
        return '{:3.1f}{}'.format(num, 'TiB')


class CallNode:
    def __init__(self, name,  source_dir=None, frame_lineno=None):
        self.name = name
        self.children = []
        self.parent = None
        self.source_dir = source_dir
        self.call_position = frame_lineno if frame_lineno else {}
    
    def add_child(self, child):
        self.children.append(child)
        child.parent = self
    
    def __iter__(self):
        return iter(self.children)

    def __repr__(self) -> str:
        return f'CallNode({self.name})'


import json
class CallNodeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, CallNode):
            return {
                'name': obj.name,
                'children': obj.children,
                'source_dir': obj.source_dir,
                'call_position': obj.call_position
            }
        return super().default(obj)
