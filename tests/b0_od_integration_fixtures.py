"""Hand-specified synthetic trajectories, not a traffic model or measured result."""
import copy
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.b0.od_integration_v1 import integration as core


class FakeBackend:
    def __init__(self, binding, condition_label="N0", *, arrival_delta_total=None,
                 queue_budget=None, exposure_count=None, active_count=0, pending_count=0,
                 censored_exposed_count=0, waiting_overflow=False, missing_output=False,
                 fail_step=None, jump_step=None, fail_permission=False, close_failure=False,
                 controls_changed_at=None, collision_at=None, restricted_entry=False,
                 wrong_loaded_input=False):
        self.binding=binding; self.condition_label=condition_label
        self.rows=core.scheduled(binding); self.by_id={r['vehicle_id']:r for r in self.rows}
        cfg=binding['scientific_configuration']
        self.routes={r['id']:tuple(r['edges'].split()) for r in cfg['route_definitions']}
        self.time=0; self.closed=False; self.output_checked=False; self.log=[]
        self.permissions={l:{'allowed':[], 'disallowed':[]} for l in (cfg['restricted_lane'],cfg['surviving_lane'])}
        self.control_snapshot=core.expected_controls(binding)
        # The fake collector derives the file identity from its actual supplied
        # input bytes, not merely from an expected SHA or a validity label.
        frozen=core.contract()
        trips=core.od_input.build_seed_allocations(frozen,binding['seed'])[binding['level']]
        self.loaded_input_xml=core.od_input.serialize_routes(frozen,binding['seed'],binding['level'],trips)+b'\n'
        if wrong_loaded_input:
            self.loaded_input_xml=self.loaded_input_xml.replace(b'depart="0"',b'depart="1"',1)
        self.control_snapshot['input_identity']['route_file_sha256']=hashlib.sha256(self.loaded_input_xml).hexdigest()
        self.fail_step=fail_step; self.jump_step=jump_step; self.fail_permission=fail_permission
        self.close_failure=close_failure; self.missing_output=missing_output
        self.controls_changed_at=controls_changed_at; self.collision_at=collision_at
        self.waiting_overflow=waiting_overflow; self.restricted_entry=restricted_entry
        disrupted=condition_label.startswith('D0')
        delta=(540 if disrupted else 0) if arrival_delta_total is None else arrival_delta_total
        budget=(567 if disrupted else 540) if queue_budget is None else queue_budget
        if type(delta) is not int or delta < 0 or type(budget) is not int or budget < 0:
            raise ValueError('invalid fixture arithmetic')
        all_ids=[r['vehicle_id'] for r in self.rows]
        self.pending=set(all_ids[-pending_count:]) if pending_count else set()
        active_candidates=[v for v in all_ids if v not in self.pending]
        self.active_at_h=set(active_candidates[-active_count:]) if active_count else set()
        target_event=[r['vehicle_id'] for r in self.rows if r['route_id']=='row1_east' and 300 < r['scheduled_departure_seconds']+11 <= 600]
        self.censored=set(target_event[:censored_exposed_count]); self.active_at_h |= self.censored
        self.event_visits=set(target_event if exposure_count is None else target_event[:exposure_count])
        if exposure_count is not None and len(self.event_visits)!=exposure_count:
            raise ValueError('fixture does not have requested event cohort')
        self.departure={v:self.by_id[v]['scheduled_departure_seconds']+1 for v in active_candidates}
        self.arrival={v:self.by_id[v]['scheduled_departure_seconds']+101+delta//540+(i<delta%540)
                      for i,v in enumerate(all_ids) if v not in self.pending and v not in self.active_at_h}
        self.halt_samples={v:budget//len(active_candidates)+(i<budget%len(active_candidates))
                           for i,v in enumerate(active_candidates)}
        if any(n>=80 for n in self.halt_samples.values()): raise ValueError('fixture budget too large')
        self.simulation=Simulation(self); self.vehicle=Vehicle(self); self.lane=Lane(self)

    def active(self):
        if self.closed: return []
        return [v for v,d in self.departure.items() if d<=self.time and (v not in self.arrival or self.time<self.arrival[v])]

    def state(self,v):
        row=self.by_id[v]; age=self.time-self.departure[v]; route=self.routes[row['route_id']]
        index=0 if age<10 else 1 if age<15 else 2 if age<80 else 3
        if v in self.censored and age>=10: index=1
        if row['route_id']=='row1_east' and 300 < self.departure[v]+10 <=600 and v not in self.event_visits and index==1:
            index=2  # explicit synthetic unobserved crossing, not inferred exposure
        edge=route[index]; lane=edge+'_1'
        if self.restricted_entry and edge=='A1B1' and 300<self.time<=600: lane='A1B1_0'
        speed=0.0 if 20<=age<20+self.halt_samples.get(v,0) else 5.0
        return dict(edge=edge,lane=lane,speed=speed,position=10.0,route_index=index)

    def simulationStep(self):
        self.log.append(('advance',self.time))
        if self.time==self.fail_step: raise OSError('synthetic step failure')
        self.time+=2 if self.time==self.jump_step else 1

    def close(self,wait=True):
        self.log.append(('close',self.time)); self.closed=True
        if self.close_failure: raise OSError('synthetic close failure')

    def controls(self,view):
        if self.time==self.controls_changed_at:
            bad=copy.deepcopy(self.control_snapshot); bad['scientific_configuration']['dynamic_rerouting']=True
            return bad
        return self.control_snapshot

    def diagnostics(self,view):
        return {'collisions':int(self.time==self.collision_at),'invalid_routes':0,'simulator_errors':0}

    def finalize_output(self):
        self.log.append(('output',self.time)); self.output_checked=True
        if not self.closed: raise AssertionError('output read before close/finalization')
        if self.missing_output: return b'<tripinfos><tripinfo'
        root=ET.Element('tripinfos')
        for i,row in enumerate(self.rows):
            v=row['vehicle_id']
            if v in self.pending: continue
            if self.departure[v]>self.time: continue
            arrive=self.arrival.get(v,-1)
            if arrive>self.time: arrive=-1
            wait=1e308 if self.waiting_overflow and i<2 else self.halt_samples[v]
            ET.SubElement(root,'tripinfo',{'id':v,'depart':str(self.departure[v]),'arrival':str(arrive),'waitingTime':str(wait)})
        return ET.tostring(root,encoding='utf-8')

    def __getattr__(self,name):
        if name.startswith(('set','change','reroute')): raise AssertionError('forbidden synthetic setter')
        raise AttributeError(name)


class Simulation:
    def __init__(self,b): self.b=b
    def getTime(self): return self.b.time
    def getDeltaT(self): return 1
    def getDepartedIDList(self): return [v for v,t in self.b.departure.items() if t==self.b.time]
    def getArrivedIDList(self): return [v for v,t in self.b.arrival.items() if t==self.b.time]
    def getStartingTeleportIDList(self): return []
    def getEndingTeleportIDList(self): return []
    def getPendingVehicles(self):
        if self.b.closed: return []
        return sorted(self.b.pending | {v for v,t in self.b.departure.items() if t>self.b.time})


class Vehicle:
    def __init__(self,b): self.b=b
    def getIDList(self): return self.b.active()
    def getVehicleClass(self,v): return 'passenger'
    def getRoadID(self,v): return self.b.state(v)['edge']
    def getLaneID(self,v): return self.b.state(v)['lane']
    def getSpeed(self,v): return self.b.state(v)['speed']
    def getLanePosition(self,v): return self.b.state(v)['position']
    def getRouteIndex(self,v): return self.b.state(v)['route_index']
    def getRoute(self,v): return self.b.routes[self.b.by_id[v]['route_id']]
    def __getattr__(self,n):
        if n.startswith(('set','change','reroute')): raise AssertionError('forbidden synthetic setter')
        raise AttributeError(n)


class Lane:
    def __init__(self,b): self.b=b
    def getAllowed(self,l): return list(self.b.permissions[l]['allowed'])
    def getDisallowed(self,l): return list(self.b.permissions[l]['disallowed'])
    def getLastStepVehicleIDs(self,l): return [v for v in self.b.active() if self.b.state(v)['lane']==l]
    def setAllowed(self,l,value):
        if l!='A1B1_0': raise AssertionError('unexpected permission lane')
        self.b.log.append(('allowed',self.b.time,tuple(value)))
        self.b.permissions[l]['allowed']=list(value)
    def setDisallowed(self,l,value):
        if l!='A1B1_0': raise AssertionError('unexpected permission lane')
        self.b.log.append(('disallowed',self.b.time,tuple(value)))
        self.b.permissions[l]['disallowed']=list(value)
        if self.b.fail_permission and self.b.time==300 and 'passenger' in value:
            raise OSError('synthetic partially applied permission failure')
    def __getattr__(self,n):
        if n.startswith(('set','change','reroute')): raise AssertionError('forbidden synthetic setter')
        raise AttributeError(n)


def good_record(repo=None,seed=20260904,level='C1',condition_label='N0',run_id=None,**options):
    binding=core.build_binding(core.repository_root() if repo is None else Path(repo),seed,level)
    backend=FakeBackend(binding,condition_label,**options)
    return core.observe_run(binding,condition_label,run_id or f'SYNTHETIC-{seed}-{level}-{condition_label}',backend,backend)
