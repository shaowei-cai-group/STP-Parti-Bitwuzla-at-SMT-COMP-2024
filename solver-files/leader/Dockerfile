################### Use BVParti
FROM smt-comp-bvparti:common AS builder
USER root

################### Extract BVParti in run stage
FROM satcomp-infrastructure:leader AS bvparti_liaison
WORKDIR /
# Copy BVParti and solver scripts

COPY --from=builder --chown=ecs-user /BVParti /competition/BVParti

COPY --chown=ecs-user resources/init_solver.sh /competition
COPY --chown=ecs-user resources/solver /competition

USER ecs-user

RUN python3 -m pip install mpi4py

RUN chmod +x /competition/BVParti/BVParti.py
RUN chmod +x /competition/init_solver.sh
RUN chmod +x /competition/solver

##//linxi-test
USER ecs-user
COPY --chown=ecs-user resources/test-files /test-files
RUN mkdir /competition/rundir
COPY resources/test-files /test-files

# ##//linxi-test
# USER root
# RUN apt-get update
# RUN apt-get -y --no-install-recommends install \
#     vim

ENTRYPOINT /competition/init_solver.sh ; exec bash