################### Use BVParti
FROM smt-comp-bvparti:common AS builder
USER root

################### Extract BVParti in run stage
FROM satcomp-infrastructure:worker AS bvparti_liaison
WORKDIR /
# Copy BVParti and solver scripts

COPY --from=builder --chown=ecs-user /BVParti /competition/BVParti

COPY --chown=ecs-user resources/init_solver.sh /competition
COPY --chown=ecs-user resources/worker /competition

USER ecs-user

RUN python3 -m pip install mpi4py

RUN chmod +x /competition/BVParti/BVParti.py
RUN chmod +x /competition/init_solver.sh
RUN chmod +x /competition/worker

##//linxi-test
RUN mkdir /competition/rundir

ENTRYPOINT /competition/init_solver.sh ; exec bash