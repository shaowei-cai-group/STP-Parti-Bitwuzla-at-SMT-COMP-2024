# STP-Parti-Bitwuzla at SMT-COMP 2024

We intend to participate in the forthcoming SMT-COMP 2024 by submitting **STP-Parti-Bitwuzla** for **the Parallel Track** and **the Cloud Track** categories.

**STP-Parti-Bitwuzla** is a **portfolio** tool based on STP and Bitwuzla, and intend for **QF_BV**. The authors of **STP-Parti-Bitwuzla** are **Mengyu Zhao, Jinkun Lin, and Shaowei Cai**.

The system description is named `STP_Parti_Bitwuzla_at_SMT_COMP_2024.pdf`.

As per the submission rule, we are providing the pseudo-random 32-bit unsigned number **998244353**.

## Variable-level Partitioning for Distributed SMT Solving

STP-Parti-Bitwuzla is the practical implementations of our innovative concept of **Var**iable-level **Parti**tioning, which is applied to the Bit-Vectors theory. This technique is introduced for the first time in our recently published paper at CAV 2024, titled *Distributed SMT Solving Based on Dynamic Variable-level Partitioning*. 

Our proposed variable-level partitioning permits robust, comprehensive partitioning. Regardless of the Boolean structure of any given instance, our partitioning algorithm can keep partitioning to the last moment of the solving process.

## Prerequisites

Docker should be installed on the machine.

Clone this repository need Git LFS (Large File Storage).

The VarParti docker images are built on top of the base containers satcomp-infrastructure:common, satcomp-infrastructure:leader and satcomp-infrastructure:worker.

The process of building these base images (as well as many other aspects of building solvers for SAT-Comp) is described in the README.md file in the [SAT-Comp and SMT-Comp Parallel and Cloud Track Instructions](https://github.com/aws-samples/aws-batch-comp-infrastructure-sample) repository.
Please follow the steps in this repository up to the point at which the base containers have been built.

## How to Build

Here is an example illustrating how to test our solver:

Build the dockers:

```bash
cd solver-files
bash build-cloud-docker-images.sh
```

Create a docker network:

```bash
docker network create smt-comp-bvp-test
```

Run the leader docker:

```bash
docker run \
    -i --shm-size=32g \
    --name leader \
    --network smt-comp-bvp-test \
    --rm \
    --user ecs-user \
    -t smt-comp-bvparti:leader
```

Run the worker docker:

```bash
docker run \
    -i --shm-size=32g \
    --name worker \
    --network smt-comp-bvp-test \
    --rm \
    --user ecs-user \
    -t smt-comp-bvparti:worker
```

Test in the leader docker:

```bash
python3 /test-files/scripts/run-parallel.py /test-files/instances/sat-7.13s.smt2
```

It will output as follows format:
The first line is the solving result, and the second is the run time.

A possible output:

```bash
sat
18.850293159484863
total cost time (start MPI and clean up):
22.26062798500061
```

```bash
python3 /test-files/scripts/run-parallel.py /test-files/instances/unsat-5.96s.smt2
```

A possible output:

```bash
unsat
10.27653431892395
total cost time (start MPI and clean up):
13.770840883255005
```
