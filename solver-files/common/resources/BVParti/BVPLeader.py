
import os
import time
import logging
from datetime import datetime
from mpi4py import MPI
from BVPTask import Task


class Leader():
    def get_current_time(self):
        return time.time() - self.start_time
    
    def init_params(self, cmd_args):
        self.input_file_path: str = cmd_args.file
        self.partitioner_path: str = cmd_args.partitioner
        self.solver_path: str = cmd_args.solver
        self.max_running_tasks: int = cmd_args.max_running_tasks
        self.time_limit: int = cmd_args.time_limit
        self.temp_folder_path = cmd_args.temp_dir
        self.output_dir_path: str = cmd_args.output_dir
        
        if not os.path.exists(self.input_file_path):
            print('file-not-found')
            assert(False)
        
        self.instance_name: str = self.input_file_path[ \
            self.input_file_path.rfind('/') + 1: self.input_file_path.find('.smt2')]
    
    def init_logging(self):
        if self.output_dir_path != None:
            logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s', 
                    filename=f'{self.output_dir_path}/log', level=logging.INFO)
        self.start_time = time.time()
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.write_line_to_log(f'start-time {formatted_time} ({self.start_time})')

    def init(self, comm_world: MPI.COMM_WORLD, cmd_args):
        
        self.comm_world = comm_world
        self.num_processes = comm_world.Get_size()
        self.idle_workers = set(range(1, self.num_processes))
        self.init_params(cmd_args)
        self.next_task_id = 0
        
        self.state_tasks_dict = {
            'generating': [],
            'generated': [],
            'simplifying': [],
            'simplified': [],
            'solving': [],
            'ended': [],
        }
        
        self.pstate_tasks_dict = {
            'not-ready': [],
            'unpartitioned': [],
            'partitioning': [],
            'partitioned': [],
            'solved': [],
        }
        
        self.tasks = []
        self.result = 'undefined'
        self.reason = -3
        self.done = False
        
        self.max_unended_tasks = self.max_running_tasks + self.max_running_tasks // 3 + 1
        
        self.base_run_cnt = 0
        self.solve_ori_flag = True
        
        # self.temp_folder_name = {generate_random_string(16)}
        # self.temp_folder_name = f'bvp-{generate_random_string(16)}'
        # self.temp_folder_name = 'bvp-test'
        
        # print(self.temp_folder_name)
        
        if not os.path.exists(self.temp_folder_path):
            os.system(f'mkdir -p {self.temp_folder_path}')
            os.system(f'mkdir -p {self.temp_folder_path}/tasks')
        
        # ##//linxi debug
        # print(self.temp_folder_path)
        # print(f'{self.output_dir_path}/log')
        
        if self.output_dir_path != None:
            if not os.path.exists(self.output_dir_path):
                os.system(f'mkdir -p {self.output_dir_path}')
        
        # os.mkdir(self.temp_folder_path)
        # os.mkdir(f'{self.temp_folder_path}/tasks')
        # if os.path.exists(self.temp_folder_path):
        #     os.system(f'rm -r {self.temp_folder_path}')
        
        self.init_logging()
        logging.info(f'temp_folder_path: {self.temp_folder_path}')
        
        # send_data = [self.partitioner_path, self.solver_path, self.temp_folder_path]
        # # self.comm_world.bcast(data, root=0)
        # for i in range(1, self.num_processes):
        #     self.comm_world.send(send_data, dest=i)
        # # self.comm_world.bcast(send_data, root=0)
        # # print('bcast done!')
        

    def write_line_to_log(self, data: str):
        logging.info(data)
    
    def make_task(self, pid):
        parent: Task = None
        if pid != -1:
            parent = self.tasks[pid]
        t = Task(self.next_task_id, parent, self.get_current_time())
        self.next_task_id += 1
        if parent != None:
            parent.subtasks.append(t)
        self.tasks.append(t)
    
    def propagate_unsat(self, t: Task, reason):
        assert(t.state != 'unsat')
        self.update_task_state(t, 'unsat')
        t.reason = reason
    
    def push_up(self, t: Task, reason):
        # only 'unsat' 'unknown' need push up
        if t.state == 'unsat':
            return
        if len(t.subtasks) == 2 and \
           t.subtasks[0].state == 'unsat' and \
           t.subtasks[1].state == 'unsat':
            self.propagate_unsat(t, reason)
            self.write_line_to_log(f'unsat-by-children {t.id} {t.subtasks[0].id} {t.subtasks[1].id}')
            if t.parent != None:
                self.push_up(t.parent, reason)
    
    def push_down(self, t: Task, reason):
        # only 'unsat' need push up
        if t.state == 'unsat':
            return
        self.propagate_unsat(t, reason)
        self.write_line_to_log(f'unsat-by-ancestor {t.id} {reason}')
        for st in t.subtasks:
            self.push_down(st, reason)

    def need_terminate(self, t: Task):
        if t.id <= 0:
            return False
        num_st = len(t.subtasks)
        st_end = 0
        if num_st > 0 and t.subtasks[0].state in ['solving', 'unsat', 'terminated']:
            st_end += 1
        if num_st > 1 and t.subtasks[1].state in ['solving', 'unsat', 'terminated']:
            st_end += 1
        
        if st_end == 0:
            return False
        if st_end == 1 and self.get_current_time() - t.time_infos['solving'] < 200.0:
            return False
        if st_end == 2 and self.get_current_time() - t.time_infos['solving'] < 100.0:
            return False
        return True
    
    def free_worker(self, id):
        # while self.comm_world.Iprobe(source=id):
        #     self.comm_world.recv(source=id)
        self.idle_workers.add(id)
    
    def update_task_state(self, t: Task, new_state: str):
        self.write_line_to_log(f'update-state {t.id} {new_state}')
        t.state = new_state
        if new_state == 'unsat':
            if t.pp != -1:
                self.write_line_to_log(f'terminate (task-{t.id}, {t.pstate}) to worker-{t.pp}')
                self.terminate(t.pp)
                self.free_worker(t.pp)
                # self.idle_workers.add(t.pp)
                t.pp = -1
                
            if t.sp != -1:
                self.write_line_to_log(f'terminate (task-{t.id}, {t.state}) to worker-{t.sp}')
                self.terminate(t.sp)
                self.free_worker(t.sp)
                # self.idle_workers.add(t.sp)
                t.sp = -1
            self.update_task_pstate(t, 'solved')
        
        if new_state in ['sat', 'unsat', 'unknown', 'terminated']:
            new_state = 'ended'
        self.state_tasks_dict[new_state].append(t)
        t.time_infos[new_state] = self.get_current_time()
        
    def update_task_pstate(self, t: Task, new_pstate: str):
        self.write_line_to_log(f'update-pstate {t.id} {new_pstate}')
        t.pstate = new_pstate
        self.pstate_tasks_dict[new_pstate].append(t)
        t.time_infos[new_pstate] = self.get_current_time()
    
    def check_process_state(self, wid, tid, running_state):
        while self.comm_world.Iprobe(source=wid):
            data = self.comm_world.recv(source=wid)
            cur_tid, task_type, result, logs = data
            self.write_line_to_log(f'### check_process_state ###')
            self.write_line_to_log(f'worker-{wid}')
            self.write_line_to_log(f'task-{tid}, current-{cur_tid}')
            self.write_line_to_log(f'running_state: {running_state}, task_type: {task_type}')
            self.write_line_to_log(f'result {result}')
            for log in logs:
                self.write_line_to_log(f'logs: {log}')
            if cur_tid == tid and task_type == running_state:
                self.write_line_to_log(f'result accepted!')
                return result
            else:
                self.write_line_to_log(f'result rejected!')
        return running_state
    
    def check_simplifying_state(self, t: Task):
        if t.state == 'unsat':
            return False
        
        sta = self.check_process_state(t.sp, t.id, 'simplifying')
        
        if sta == 'simplifying':
            return True
        
        if sta == 'simplified':
            # instance_path = f'{self.temp_folder_path}/tasks/task-{t.id}-simplified.smt2'
            # if not os.path.exists(instance_path):
            #     with open(instance_path, 'bw') as file:
            #         file.write(res_data)
            t.sim_pos = t.sp
        
        
        self.free_worker(t.sp)
        # self.idle_workers.add(t.sp)
        t.sp = -1
        self.update_task_state(t, 'simplified')
        self.update_task_pstate(t, 'unpartitioned')
        return False
    
    def check_partitioning_pstate(self, t: Task):
        if t.pstate == 'solved':
            return False
            
        sta = self.check_process_state(t.pp, t.id, 'partitioning')
        if sta == 'partitioning':
            return True

        if sta == 'partitioned':
            # instance_path = f'{self.temp_folder_path}/tasks/task-{res_data[0][0]}.smt2'
            # if not os.path.exists(instance_path):
            #     with open(instance_path, 'bw') as file:
            #         file.write(res_data[0][1])
                    
            # instance_path = f'{self.temp_folder_path}/tasks/task-{res_data[1][0]}.smt2'
            # if not os.path.exists(instance_path):
            #     with open(instance_path, 'bw') as file:
            #         file.write(res_data[1][1])
            
            t.subtasks[0].ori_pos = t.pp
            t.subtasks[1].ori_pos = t.pp
            self.update_task_state(t.subtasks[0], 'generated')
            self.update_task_state(t.subtasks[1], 'generated')
            
        self.free_worker(t.pp)
        # self.idle_workers.add(t.pp)
        t.pp = -1
        self.update_task_pstate(t, sta)
        return False
    
    # True for still running
    def check_solving_state(self, t: Task):
        if t.state in ['unsat', 'unknown', 'terminated']:
            return False
        
        sta = self.check_process_state(t.sp, t.id, 'solving')
        
        if sta == 'solving':
            return True
            # if self.need_terminate(t):
            #     self.update_task_state(t, 'terminated')
            #     self.terminate(t.sp)
            #     self.idle_workers.add(t.sp)
            #     t.sp = -1
            #     return False
            # else:
            #     return True
        
        self.free_worker(t.sp)
        # self.idle_workers.add(t.sp)
        t.sp = -1
        
        if sta == 'sat':
            self.result = 'sat'
            self.reason = t.id
            self.done = True
            self.write_line_to_log(f'sat-task {t.id}')
            return False
        
        t.reason = t.id
        if sta == 'unsat':
            self.update_task_state(t, 'unsat')
            if t.parent != None:
                self.push_up(t.parent, t.id)
            
            for st in t.subtasks:
                self.push_down(st, t.id)
        else:
            self.update_task_state(t, 'unknown')
            self.write_line_to_log(f'unknown-node {t.id} {sta}')
        
        return False
    
    def check_runnings_state(self):
        if self.solve_ori_flag and self.ori_task.state == 'solving':
            sta = self.check_process_state(self.ori_task.sp, -1, 'solving')
            # sta = self.check_solving_process(self.ori_task.id, self.ori_task.sp)
            if sta != 'solving':
                # print(f'result: {sta}')
                assert(sta in ['sat', 'unsat'])
                self.result = sta
                self.done = True
                self.write_line_to_log(f'solved-by-original {sta}')
                return
        
        still_solvings = []
        for t in self.state_tasks_dict['solving']:
            t: Task
            if t.state != 'solving':
                continue
            if self.check_solving_state(t):
                still_solvings.append(t)
            else:
                if self.done:
                    return
        self.state_tasks_dict['solving'] = still_solvings
        
        if len(self.tasks) > 0:
            root_task: Task = self.tasks[0]
            if root_task.state == 'unsat':
                self.result = 'unsat'
                self.reason = root_task.reason
                self.done = True
                self.write_line_to_log(f'unsat-root-task {root_task.reason}')
                return
        
        still_simplifyings = []
        for t in self.state_tasks_dict['simplifying']:
            t: Task
            if t.state != 'simplifying':
                continue
            if self.check_simplifying_state(t):
                still_simplifyings.append(t)
        self.state_tasks_dict['simplifying'] = still_simplifyings
        
        still_partitionings = []
        for t in self.pstate_tasks_dict['partitioning']:
            if self.check_partitioning_pstate(t):
                still_partitionings.append(t)
        self.pstate_tasks_dict['partitioning'] = still_partitionings
    
    def assign_task(self, task_id, task_type_data, instance_data_info):
        worker_id = self.idle_workers.pop()
        self.write_line_to_log(f'assign (task-{task_id}, {task_type_data}) to worker-{worker_id}')
        # data = pickle.dumps((task_id, task_type_data, instance_data_info))
        # req = self.comm_world.Isend(data, dest=worker_id, tag=0)
        # req.Wait()
        send_data = (task_id, task_type_data, instance_data_info)
        self.comm_world.send(send_data, dest=worker_id, tag=0)
        return worker_id
    
    def simplify_task(self, t: Task):
        instance_path = f'{self.temp_folder_path}/tasks/task-{t.id}.smt2'
        cmd =  [self.partitioner_path,
                instance_path,
                '--partition.output-dir', self.temp_folder_path,
                '--partition.next-id', f'{t.id}',
                '--partition.simplify', '1',
            ]
        self.write_line_to_log('exec-command {}'.format(' '.join(cmd)))
        instance_data = None
        if t.ori_pos == 0:
            with open(instance_path, 'br') as file:
                instance_data = file.read()
            
        t.sp = self.assign_task(t.id, ['simplifying'], [t.ori_pos, instance_data])
        
        self.update_task_state(t, 'simplifying')
    
    def partition_task(self, t: Task):
        instance_path = f'{self.temp_folder_path}/tasks/task-{t.id}-simplified.smt2'
        cmd =  [self.partitioner_path,
                instance_path, 
                '--partition.output-dir', self.temp_folder_path,
                '--partition.next-id', f'{self.next_task_id}',
                '--partition.simplify', '0',
            ]
        self.write_line_to_log('exec-command {}'.format(' '.join(cmd)))
        
        # with open(instance_path, 'br') as file:
        #     instance_data = file.read()
        
        t.pp = self.assign_task(t.id, ['partitioning', self.next_task_id], [t.sim_pos, None])
        
        self.update_task_pstate(t, 'partitioning')
        self.make_task(t.id)
        self.make_task(t.id)
    
    def solve_task(self, t: Task):
        instance_path = f'{self.temp_folder_path}/tasks/task-{t.id}-simplified.smt2'
        cmd =  [self.solver_path,
                instance_path,
            ]
        self.write_line_to_log('exec-command {}'.format(' '.join(cmd)))
        
        # with open(instance_path, 'br') as file:
        #     instance_data = file.read()
        t.sp = self.assign_task(t.id, ['solving'], [t.sim_pos, None])
        
        self.update_task_state(t, 'solving')
    
    def get_running_num(self):
        return len(self.state_tasks_dict['simplifying']) \
             + len(self.pstate_tasks_dict['partitioning']) \
             + len(self.state_tasks_dict['solving']) \
             + self.base_run_cnt
    
    def get_unended_num(self):
        return len(self.tasks) \
             - len(self.state_tasks_dict['ended'])
    
    def simplify_generated_tasks(self):
        # running_num = self.get_running_num()
        # if running_num >= self.max_running_tasks:
        #     return
        still_generateds = []
        for t in self.state_tasks_dict['generated']:
            t: Task
            if t.state != 'generated':
                continue
            # if running_num >= self.max_running_tasks:
            if len(self.idle_workers) == 0:
                still_generateds.append(t)
            else:
                self.simplify_task(t)
                # running_num += 1
                self.write_line_to_log(f'running: {self.get_running_num()}, unended: {self.get_unended_num()}')
        self.state_tasks_dict['generated'] = still_generateds
    
    def partition_unpartitioned_tasks(self):
        # running_num = self.get_running_num()
        unended_num = self.get_unended_num()
        # if running_num >= self.max_running_tasks \
        if len(self.idle_workers) == 0 \
           or unended_num >= self.max_unended_tasks:
            return
        
        still_unpartitioneds = []
        for t in self.pstate_tasks_dict['unpartitioned']:
            t: Task
            if t.pstate != 'unpartitioned':
                continue
            # if running_num >= self.max_running_tasks \
            if len(self.idle_workers) == 0 \
               or unended_num >= self.max_unended_tasks:
                still_unpartitioneds.append(t)
            else:
                self.partition_task(t)
                # running_num += 1
                unended_num += 2
                self.write_line_to_log(f'running: {self.get_running_num()}, unended: {self.get_unended_num()}')
        self.pstate_tasks_dict['unpartitioned'] = still_unpartitioneds
    
    def solve_simplified_tasks(self):
        # running_num = self.get_running_num()
        # if running_num >= self.max_running_tasks:
        if len(self.idle_workers) == 0:
            return
        still_simplifieds = []
        for t in self.state_tasks_dict['simplified']:
            t: Task
            if t.state != 'simplified':
                continue
            # if running_num >= self.max_running_tasks:
            if len(self.idle_workers) == 0:
                still_simplifieds.append(t)
            else:
                self.solve_task(t)
                # running_num += 1
                self.write_line_to_log(f'running: {self.get_running_num()}, unended: {self.get_unended_num()}')
        self.state_tasks_dict['simplified'] = still_simplifieds
    
    def solve_ori_task(self):
        # run original task
        self.ori_task = Task(-2, None, self.get_current_time())
        instance_path = f'{self.temp_folder_path}/tasks/task-0.smt2'
        cmd =  [self.solver_path,
                instance_path
            ]
        self.write_line_to_log('exec-command {}'.format(' '.join(cmd)))
        
        with open(self.input_file_path, 'br') as file:
            instance_data = file.read()
        
        self.ori_task.sp = self.assign_task(-1, ['solving'], [0, instance_data])
        
        self.ori_task.state = 'solving'
        self.ori_task.time_infos['solving'] = self.get_current_time()
        self.base_run_cnt += 1
    
    def init_root_task(self):
        # self.write_line_to_log(f'cp {self.input_file_path} {self.temp_folder_path}/tasks/tasks/tasks/task-0.smt2')
        os.system(f'cp {self.input_file_path} {self.temp_folder_path}/tasks/task-0.smt2')
        self.make_task(-1)
        rt: Task = self.tasks[0]
        rt.ori_pos = 0
        self.update_task_state(rt, 'generated')
        self.update_task_pstate(rt, 'not-ready')
    
    def solve(self):
        if self.solve_ori_flag:
            self.solve_ori_task()
        self.init_root_task()
        while True:
            self.check_runnings_state()
            if self.done:
                return
            self.simplify_generated_tasks()
            self.partition_unpartitioned_tasks()
            self.solve_simplified_tasks()
            if self.time_limit != 0 and \
               self.get_current_time() >= self.time_limit:
                raise TimeoutError()
            
            # if self.get_running_num() >= self.max_running_tasks:
            if len(self.idle_workers) == 0:
                time.sleep(0.1)
                # self.full_work_cnt = self.full_work_cnt + 1
                # if self.full_work_cnt == 30:
                #     self.worker_can_sleep()

    def terminate(self, wid):
        # data = pickle.dumps(None)
        # req = self.comm_world.Isend(data, dest=wid, tag=1)
        # req.Wait()
        self.comm_world.send(None, dest=wid, tag=1)
    
    def clean_up(self):
        # for i in range(1, self.num_processes):
        #     send_data = pickle.dumps(None)
        #     self.comm_world.Ssend(send_data, dest=i, tag=2)
        #     self.comm_world.recv(source=i)
        #     print(f'worker {i} is killed')
        
        if os.path.exists(self.temp_folder_path):
            os.system(f'rm -r {self.temp_folder_path}')
            
    
    def __call__(self, comm_world: MPI.COMM_WORLD, cmd_args):
        self.init(comm_world, cmd_args)
        try:
            self.solve()
        except TimeoutError:
            self.result = 'timeout'
            self.write_line_to_log('timeout')
        # except AssertionError as ae:
        #     self.result = 'AssertionError'
        #     # print(f'AssertionError: {ae}')
        #     # self.write_line_to_log(f'AssertionError: {ae}')
        # except Exception as e:
        #     self.result = 'Exception'
        #     # print(f'Exception: {e}')
        #     # self.write_line_to_log(f'Exception: {e}')
        
        end_time = time.time()
        execution_time = end_time - self.start_time
        print(self.result)
        print(execution_time)
        
        if self.output_dir_path != None:
            with open(f'{self.output_dir_path}/result.txt', 'w') as f:
                f.write(f'{self.result}\n{execution_time}\n')
            # os.system(f'cp {self.temp_folder_path}/log {self.output_dir_path}/log')
            # with open(f'{self.output_dir_path}/temp_folder.txt', 'w') as f:
            #     f.write(f'{self.temp_folder_path}')
                
        # self.kill_all()
        # self.clean_up()
        # clean_up_time = time.time() - end_time
        # print(f'clean up time: {clean_up_time}')
        # MPI.Finalize()
        comm_world.Abort()
    
