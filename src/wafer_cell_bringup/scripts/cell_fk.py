# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""Forward kinematics straight off cell.urdf — no assumptions about DH."""
import numpy as np, xml.etree.ElementTree as ET, math

def rpy(r,p,y):
    cr,sr,cp,sp,cy,sy=math.cos(r),math.sin(r),math.cos(p),math.sin(p),math.cos(y),math.sin(y)
    return (np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]])@
            np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])@
            np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]]))

def T(R,t):
    M=np.eye(4); M[:3,:3]=R; M[:3,3]=t; return M

class Chain:
    def __init__(self, path):
        r=ET.parse(path).getroot()
        self.j={}
        for j in r.findall('joint'):
            o=j.find('origin')
            xyz=[float(v) for v in (o.get('xyz','0 0 0') if o is not None else '0 0 0').split()]
            rr =[float(v) for v in (o.get('rpy','0 0 0') if o is not None else '0 0 0').split()]
            ax=j.find('axis')
            a=[float(v) for v in (ax.get('xyz') if ax is not None else '0 0 1').split()]
            self.j[j.get('name')]=dict(type=j.get('type'), parent=j.find('parent').get('link'),
                                       child=j.find('child').get('link'), xyz=np.array(xyz),
                                       rpy=rr, axis=np.array(a,dtype=float))
        self.parent_of={v['child']:k for k,v in self.j.items()}
    def pose(self, link, q):
        M=np.eye(4)
        chain=[]
        while link in self.parent_of:
            jn=self.parent_of[link]; chain.append(jn); link=self.j[jn]['parent']
        assert link=='world', link
        for jn in reversed(chain):
            d=self.j[jn]
            M=M@T(rpy(*d['rpy']), d['xyz'])
            v=q.get(jn,0.0)
            if d['type']=='revolute' or d['type']=='continuous':
                a=d['axis']/np.linalg.norm(d['axis']); c,s=math.cos(v),math.sin(v)
                K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]])
                M=M@T(np.eye(3)+s*K+(1-c)*K@K, np.zeros(3))
            elif d['type']=='prismatic':
                M=M@T(np.eye(3), d['axis']*v)
        return M
