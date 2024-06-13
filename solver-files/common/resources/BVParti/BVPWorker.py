from mpi4py import MPI
import subprocess
import time
import os

class Worker():
    
    def write_line_to_log(self, info: str):
        self.logs.append(info)

    def check_process(self, p: subprocess.Popen):
        rc = p.poll()
        if rc == None:
            return ['running']
        out_data, err_data = p.communicate()
        return ['done', rc, out_data, err_data]

    def check_simplifying_process(self, id, p: subprocess.Popen):
        res = self.check_process(p)
        if res[0] == 'running':
            return 'simplifying'
        rc, out_data, err_data = res[1], res[2], res[3]
        ret = 'simplified'
        lines = out_data.split('\n')
        self.write_line_to_log(f'simplifying-result id {id}')
        for line in lines:
            self.write_line_to_log(f'simplifying-result {line}')
        # if True:
        #     print(rc)
        #     print(f'out_data: {out_data}, err_data: {err_data}')
        if rc != 0:
            ret = 'non-zero-return'
            raise AssertionError()
        self.write_line_to_log(f'task-simplified {id} {ret}')
        return ret

    
    def check_solving_process(self, id, p: subprocess.Popen):
        res = self.check_process(p)
        if res[0] == 'running':
            return 'solving'
        rc, out_data, err_data = res[1], res[2], res[3]
        ret: str = out_data.strip('\n').strip(' ')
        ret = 'unknown'
        lines = out_data.split('\n')
        self.write_line_to_log(f'solving-result id {id}')
        for line in lines:
            words = line.split(' ')
            if len(words) <= 0:
                continue
            if ret == 'unknown' and words[0] != 'c':
                ret = line
            self.write_line_to_log(f'solving-result {line}')
        # # debug
        # if True:
        #     print(rc)
        #     print(f'out_data: {out_data}, err_data: {err_data}')
        # self.write_line_to_log(f'return-code {rc}')
        # if rc != 0:
        #     ret = 'non-zero-return'
        #     raise AssertionError()
        self.write_line_to_log(f'task-solved {id} {ret}')
        return ret
    
    def check_partitioning_process(self, id, p: subprocess.Popen):
        res = self.check_process(p)
        if res[0] == 'running':
            return 'partitioning'
        rc, out_data, err_data = res[1], res[2], res[3]
        ret = 'partitioned'
        lines = out_data.split('\n')
        self.write_line_to_log(f'partitioning-result id {id}')
        for line in lines:
            self.write_line_to_log(f'partitioning-result {line}')
        # if False:
        #     print(rc)
        #     print(f'out_data: {out_data}, err_data: {err_data}')
        if rc != 0:
            # ret = 'non-zero-return'
            if rc == 233:
                ret = 'solved'
            else:
                raise AssertionError()
        self.write_line_to_log(f'task-partitioned {id} {ret}')
        return ret
    
    def __call__(self, comm_world: MPI.COMM_WORLD, wid, cmd_args):
        # p = None
        status = 'idle'
        recv_data = None
        
        temp_folder_path = cmd_args.temp_dir
        partitioner_path = cmd_args.partitioner
        solver_path = cmd_args.solver
        
        if not os.path.exists(temp_folder_path):
            os.system(f'mkdir -p {temp_folder_path}')
            os.system(f'mkdir -p {temp_folder_path}/tasks')
            
        # print(temp_folder_path)
        while True:
            if status == 'running':
                self.logs = []
                if task_type == 'simplifying':
                    result = self.check_simplifying_process(task_id, p)
                elif task_type == 'solving':
                    result = self.check_solving_process(task_id, p)
                elif task_type == 'partitioning':
                    result = self.check_partitioning_process(task_id, p)
                else:
                    assert(False)
                if result not in ['simplifying', 'solving', 'partitioning']:
                    # send_data = pickle.dumps((task_id, task_type, result, self.logs))
                    # req = comm_world.Isend(send_data, dest=0)
                    # req.Wait()
                    
                    send_data = (task_id, task_type, result, self.logs)
                    comm_world.send(send_data, dest=0)
                    status = 'idle'
                time.sleep(0.2)
            
            if not comm_world.Iprobe(source=MPI.ANY_SOURCE):
                time.sleep(0.1)
                continue
            
            msg_status = MPI.Status()
            recv_data = comm_world.recv(source=MPI.ANY_SOURCE, status=msg_status)
            status_tag = msg_status.Get_tag()
            source_rank = msg_status.Get_source()

            if source_rank == 0:
                if status_tag == 0:
                    # if status != 'idle':
                    #     old_tid = task_id
                    # assert(status == 'idle')
                    task_id, task_type_datas, instance_data_info = recv_data
                    
                    instance_pos = instance_data_info[0]
                    instance_data = instance_data_info[1]
                    task_type = task_type_datas[0]
                    
                    if status != 'idle':
                        # print(f'status: {status}, task_id: {old_tid}, new tid: {task_id}')
                        # print(f'task_type: {task_type}, instance_pos: {instance_pos}')
                        assert(False)
                    
                    if task_type == 'simplifying':
                        instance_path = f'{temp_folder_path}/tasks/task-{task_id}.smt2'
                        cmd =  [partitioner_path,
                                instance_path,
                                '--partition.output-dir', temp_folder_path,
                                '--partition.next-id', f'{task_id}',
                                '--partition.simplify', '1',
                            ]
                    elif task_type == 'solving':
                        if task_id == -1:
                            instance_path = f'{temp_folder_path}/tasks/task-0.smt2'
                        else:
                            instance_path = f'{temp_folder_path}/tasks/task-{task_id}-simplified.smt2'
                        cmd =  [solver_path,
                                instance_path,
                            ]
                    elif task_type == 'partitioning':
                        next_task_id = task_type_datas[1]
                        instance_path = f'{temp_folder_path}/tasks/task-{task_id}-simplified.smt2'
                        cmd =  [partitioner_path,
                                instance_path, 
                                '--partition.output-dir', temp_folder_path,
                                '--partition.next-id', f'{next_task_id}',
                                '--partition.simplify', '0',
                            ]
                    else:
                        assert(False)
                    
                    if instance_pos == 0:
                        if not os.path.exists(instance_path):
                            with open(instance_path, 'bw') as file:
                                file.write(instance_data)
                        # time.sleep(0.1)

                    if os.path.exists(instance_path):
                        status = 'running'
                        p = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                    else:
                        assert(instance_pos != wid)
                        status = 'waiting-data'
                        # send_data = pickle.dumps(instance_path)
                        # req = comm_world.Isend(send_data, dest=instance_pos, tag=0)
                        # req.Wait()
                        
                        send_data = instance_path
                        comm_world.send(send_data, dest=instance_pos, tag=0)
                    # self.write_line_to_log(f'task {task_id} {status}, instance_pos: {instance_pos}')
                elif status_tag == 1:
                    p: subprocess.Popen
                    if status == 'running':
                        p.terminate()
                    status = 'idle'
                # elif status_tag == 2:
                #     p: subprocess.Popen
                #     print(f'worker {wid} receive kill signal')
                #     if status == 'running':
                #         p.terminate()
                #     break
                else:
                    assert(False)
            else:
                if status_tag == 0:
                    # query data
                    # self.write_line_to_log(f'query from {source_rank} for instance {query_instance_path}')
                    query_instance_path = recv_data
                    with open(query_instance_path, 'br') as file:
                        query_instance_data = file.read()
                    # send_data = pickle.dumps((query_instance_path, query_instance_data))
                    # req = comm_world.Isend(send_data, dest=source_rank, tag=1)
                    # req.Wait()
                    
                    send_data = (query_instance_path, query_instance_data)
                    comm_world.send(send_data, dest=source_rank, tag=1)
                elif status_tag == 1:
                    # response data
                    response_instance_path, response_instance_data = recv_data
                    # self.write_line_to_log(f'response from {source_rank} for instance {response_instance_path}')
                    # print(f'response from {source_rank} for instance {response_instance_path}')
                    if status == 'waiting-data' and response_instance_path == instance_path:
                        if not os.path.exists(instance_path):
                            with open(instance_path, 'bw') as file:
                                file.write(response_instance_data)
                        status = 'running'
                        p = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                else:
                    assert(False)
        # print(f'worker {wid} is ready')
        # if os.path.exists(temp_folder_path):
        #     os.system(f'rm -r {temp_folder_path}')
        # comm_world.send(None, dest=0)
        

