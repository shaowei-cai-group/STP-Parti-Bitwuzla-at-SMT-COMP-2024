
class Task():
    # sp: solving process
    # pp: partitioning process
    def __init__(self, id, parent, make_time):
        self.sp = -1
        self.pp = -1
        self.id = id
        self.parent = parent
        self.time_infos = {'make': make_time}
        self.ori_pos = -1
        self.sim_pos = -1
        # generating
        # waiting
        # simplifying simplified
        # solving
        # sat unsat unknown
        # generating  | -> waiting     BY (partition done)
        # waiting     | -> simplifying BY (simplify task)
        # simplifying | -> simplified  BY (simplification done)
        # simplified  | -> solving     BY (run task)
        # solving     | -> sat, unsat  BY (solver)
        # 
        # generating  |
        # waiting     |
        # simplifying |
        # simplified  |
        # solving     |
        #               -> unsat       BY (ancester, children, partitioner)
        #               -> unknown     BY (children)
        self.state = 'generating'
        # not-ready unpartitioned partitioning partitioned solved
        self.pstate = 'not-ready'
        self.reason = -3
        self.subtasks = []
        
    def __str__(self) -> str:
        pid = -1
        if (self.parent != None):
            pid = self.parent.id
        ret = f'id: {self.id}'
        ret += f', parent: {pid}'
        ret += f', state: {self.state}'
        if self.reason != -3:
            ret += f', reason: {self.reason}'
        if len(self.subtasks) > 0:
            stid = [self.subtasks[0].id, self.subtasks[1].id]
            ret += f', subtasks: {stid}'
        ret += f'\ntime-infos: {self.time_infos}\n'
        return ret

