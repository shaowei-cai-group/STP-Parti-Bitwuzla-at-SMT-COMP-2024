#!/bin/bash

cd common
docker build -t smt-comp-bvparti:common .
cd ../leader
docker build -t smt-comp-bvparti:leader .

