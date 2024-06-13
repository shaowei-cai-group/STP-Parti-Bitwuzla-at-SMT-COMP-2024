################### Init
FROM satcomp-infrastructure:common
USER root
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get -y --no-install-recommends install \
    build-essential \
    libopenmpi-dev \
    python3.8

# ##//linxi-test
# RUN apt-get -y --no-install-recommends install \
#     vim

# # ----------------
# # BVParti Builder Image
# # ----------------
# # >> Includes build files and test instances

COPY resources/BVParti /BVParti
RUN chmod +x /BVParti/BVParti.py
